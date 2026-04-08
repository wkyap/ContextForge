"""FastAPI application — lifespan, middleware, routers, exception handling."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from contextforge.agents.graph import create_agent
from contextforge.api.v1 import (
    admin,
    agents,
    connectors,
    courses,
    employers,
    governance,
    graph,
    health,
    onboarding,
    openings,
    pipelines,
    placements,
    reports,
    search,
    skills,
    timeseries,
    trainees,
    ws,
)
from contextforge.connectors.base import LoggingSink
from contextforge.connectors.runtime import ConnectorSupervisor
from contextforge.connectors.sinks import CompositeSink, KGSink, TimescaleSink
from contextforge.config import get_settings
from contextforge.db.migrations import run_all_migrations
from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.redis import RedisClient
from contextforge.db.timescale import TimescaleClient
from contextforge.observability.langfuse_setup import init_langfuse, shutdown_langfuse
from contextforge.skills.registry import SkillRegistry
from contextforge.skills.watcher import watch_skills

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start DB clients, run migrations, then tear down on shutdown."""
    settings = get_settings()

    # Build clients
    postgres = PostgresClient(settings.postgres_dsn)
    timescale = TimescaleClient(settings.timescale_dsn)
    neo4j = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    qdrant = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
        embedding_dim=settings.embedding_dim,
    )
    redis = RedisClient(settings.redis_url)

    # Connect all
    await postgres.connect()
    await timescale.connect()
    await neo4j.connect()
    await qdrant.connect()
    await redis.connect()

    # Run migrations
    await run_all_migrations(postgres, timescale, neo4j, qdrant)

    # Observability
    init_langfuse(settings)

    # Agent runtime
    agent, checkpointer_ctx = await create_agent(settings)

    # Skill registry — lazy load + hot-reload watcher
    domains_dir = Path(__file__).resolve().parents[2] / "domains"
    skill_registry = SkillRegistry(root=domains_dir if domains_dir.exists() else None)
    # Eager-load once so the catalog is warm on first request; hot-reload picks up
    # subsequent edits without an API restart.
    if domains_dir.exists():
        skill_registry.load_from_directory(domains_dir)
        skill_watch_stop = asyncio.Event()
        skill_watch_task = asyncio.create_task(
            watch_skills(skill_registry, domains_dir, skill_watch_stop)
        )
    else:
        skill_watch_stop = None
        skill_watch_task = None

    # Store on app.state for dependency injection
    app.state.postgres = postgres
    app.state.timescale = timescale
    app.state.neo4j = neo4j
    app.state.qdrant = qdrant
    app.state.redis = redis
    app.state.agent = agent
    app.state.checkpointer_ctx = checkpointer_ctx
    app.state.skill_registry = skill_registry

    # Connector supervisor (Phase 2.1+2.3) — CompositeSink routes records to
    # KG (entity-shaped), Timescale (numeric telemetry), or Logging (fallback).
    composite_sink = CompositeSink(
        kg=KGSink(neo4j),
        timescale=TimescaleSink(timescale),
        fallback=LoggingSink(),
    )
    connector_supervisor = ConnectorSupervisor(sink=composite_sink)
    app.state.connector_supervisor = connector_supervisor

    # Auto-start any connector SKILL.md entries flagged with autostart: true
    try:
        await connector_supervisor.autostart_from_registry(skill_registry)
    except Exception:
        logger.exception("Connector autostart sweep failed")

    logger.info("ContextForge engine started (env=%s)", settings.env)

    yield

    # Shutdown
    try:
        await app.state.connector_supervisor.shutdown()
    except Exception:
        logger.exception("Connector supervisor shutdown failed")
    if skill_watch_task is not None:
        assert skill_watch_stop is not None
        skill_watch_stop.set()
        skill_watch_task.cancel()
        try:
            await skill_watch_task
        except (asyncio.CancelledError, Exception):
            pass
    await app.state.checkpointer_ctx.__aexit__(None, None, None)
    shutdown_langfuse()
    await redis.disconnect()
    await qdrant.disconnect()
    await neo4j.disconnect()
    await timescale.disconnect()
    await postgres.disconnect()
    logger.info("ContextForge engine stopped")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ContextForge Engine",
        description="AI-native, sector-agnostic context engineering platform",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    prefix = "/api/v1"
    app.include_router(health.router,      prefix=prefix, tags=["health"])
    app.include_router(skills.router,      prefix=prefix, tags=["skills"])
    app.include_router(graph.router,       prefix=prefix, tags=["graph"])
    app.include_router(timeseries.router,  prefix=prefix, tags=["timeseries"])
    app.include_router(search.router,      prefix=prefix, tags=["search"])
    app.include_router(agents.router,      prefix=prefix, tags=["agents"])
    app.include_router(governance.router,  prefix=prefix, tags=["governance"])
    app.include_router(onboarding.router,  prefix=prefix, tags=["onboarding"])
    app.include_router(pipelines.router,   prefix=prefix, tags=["pipelines"])
    app.include_router(connectors.router,  prefix=prefix, tags=["connectors"])
    app.include_router(admin.router,       prefix=prefix, tags=["admin"])
    app.include_router(ws.router,          prefix=prefix, tags=["websocket"])

    # ── CareerForge domain routes ────────────────────────────────────
    app.include_router(trainees.router,    prefix=prefix, tags=["trainees"])
    app.include_router(courses.router,     prefix=prefix, tags=["courses"])
    app.include_router(employers.router,   prefix=prefix, tags=["employers"])
    app.include_router(openings.router,    prefix=prefix, tags=["openings"])
    app.include_router(placements.router,  prefix=prefix, tags=["placements"])
    app.include_router(reports.router,     prefix=prefix, tags=["reports"])

    # ── Global exception handler ──────────────────────────────────────────
    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
