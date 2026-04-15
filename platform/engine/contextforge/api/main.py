"""FastAPI application — lifespan, middleware, routers, exception handling."""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Make the repo-level ``apps/`` tree importable as ``apps.<name>``. The engine
# is installed as the ``contextforge`` package; apps live outside that package
# and are loaded at runtime per CONTEXTFORGE_APPS_ENABLED.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from contextforge.agents.graph import create_agent  # noqa: E402
from contextforge.api.v1 import (  # noqa: E402
    admin,
    agent_configs,
    agents,
    connectors,
    governance,
    graph,
    health,
    onboarding,
    pipelines,
    quality,
    search,
    skills,
    tenants,
    timeseries,
    ws,
)
from contextforge.config import get_settings  # noqa: E402
from contextforge.connectors.base import LoggingSink  # noqa: E402
from contextforge.connectors.config_repo import ConnectorConfigRepo  # noqa: E402
from contextforge.connectors.dlq import DLQRepository  # noqa: E402
from contextforge.connectors.runtime import ConnectorSupervisor  # noqa: E402
from contextforge.connectors.sinks import (  # noqa: E402
    CompositeSink,
    KGSink,
    TimescaleSink,
    VectorSink,
)
from contextforge.db.migrations import run_all_migrations  # noqa: E402
from contextforge.db.neo4j import Neo4jClient  # noqa: E402
from contextforge.db.postgres import PostgresClient  # noqa: E402
from contextforge.db.qdrant import QdrantClient  # noqa: E402
from contextforge.db.redis import RedisClient  # noqa: E402
from contextforge.db.timescale import TimescaleClient  # noqa: E402
from contextforge.knowledge.embedding_service import EmbeddingService  # noqa: E402
from contextforge.observability.langfuse_setup import (  # noqa: E402
    init_langfuse,
    shutdown_langfuse,
)
from contextforge.skills.registry import SkillRegistry  # noqa: E402
from contextforge.skills.watcher import watch_skills  # noqa: E402

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start DB clients, run migrations, then tear down on shutdown."""
    settings = get_settings()

    # Build clients
    postgres = PostgresClient(settings.postgres_dsn, app_names=settings.enabled_apps)
    timescale = TimescaleClient(settings.timescale_dsn, app_names=settings.enabled_apps)
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

    # Run migrations (platform first, then per-app)
    repo_root = Path(__file__).resolve().parents[4]
    apps_root = repo_root / settings.apps_dir
    await run_all_migrations(
        postgres,
        timescale,
        neo4j,
        qdrant,
        apps_root=apps_root,
        enabled_apps=settings.enabled_apps,
    )

    # Observability
    init_langfuse(settings)

    # Agent runtime
    agent, checkpointer_ctx = await create_agent(settings)

    # Skill registry — iterate enabled apps and load their SKILL.md packs.
    # (repo_root / apps_root already resolved above for migrations.)
    app_skill_dirs = [
        apps_root / name / "skills"
        for name in settings.enabled_apps
        if (apps_root / name / "skills").exists()
    ]
    skill_registry = SkillRegistry(root=apps_root if apps_root.exists() else None)
    skill_watch_stop: asyncio.Event | None = None
    skill_watch_task: asyncio.Task[None] | None = None
    if app_skill_dirs:
        for skills_dir in app_skill_dirs:
            skill_registry.load_from_directory(skills_dir)
        # Hot-reload watcher spans all enabled app skill dirs.
        skill_watch_stop = asyncio.Event()
        skill_watch_task = asyncio.create_task(
            watch_skills(skill_registry, app_skill_dirs[0], skill_watch_stop)
        )
    else:
        logger.warning(
            "No app skill directories found under %s for enabled apps %r",
            apps_root,
            settings.enabled_apps,
        )

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
    embedder = EmbeddingService(settings)
    kg_sink = KGSink(neo4j)
    ts_sink = TimescaleSink(timescale)
    vec_sink = VectorSink(qdrant, embedder)
    log_sink = LoggingSink()
    composite_sink = CompositeSink(
        kg=kg_sink, timescale=ts_sink, vector=vec_sink, fallback=log_sink,
    )
    dlq_repo = DLQRepository(postgres)
    connector_supervisor = ConnectorSupervisor(sink=composite_sink, dlq=dlq_repo)
    app.state.connector_dlq = dlq_repo
    # Register named sinks so persisted connector configs can pick one via `sink`.
    connector_supervisor.register_sink("kg", kg_sink)
    connector_supervisor.register_sink("timescale", ts_sink)
    connector_supervisor.register_sink("vector", vec_sink)
    connector_supervisor.register_sink("composite", composite_sink)
    connector_supervisor.register_sink("logging", log_sink)
    app.state.connector_supervisor = connector_supervisor

    # Auto-start: SKILL.md flagged with autostart: true, then enabled DB configs.
    try:
        await connector_supervisor.autostart_from_registry(skill_registry)
    except Exception:
        logger.exception("Connector autostart sweep (registry) failed")
    try:
        await connector_supervisor.autostart_from_db(ConnectorConfigRepo(postgres))
    except Exception:
        logger.exception("Connector autostart sweep (db) failed")

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

    # ── Multi-tenant middleware ───────────────────────────────────────────
    from contextforge.tenancy.middleware import TenantMiddleware

    app.add_middleware(TenantMiddleware)

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
    app.include_router(tenants.router,       prefix=prefix, tags=["tenants"])
    app.include_router(agent_configs.router, prefix=prefix, tags=["agent-configs"])
    app.include_router(quality.router,     prefix=prefix, tags=["quality"])
    app.include_router(admin.router,       prefix=prefix, tags=["admin"])
    app.include_router(ws.router,          prefix=prefix, tags=["websocket"])

    # ── App routers (one module per enabled app) ─────────────────────
    for name in settings.enabled_apps:
        module_path = f"apps.{name}.api"
        try:
            app_api = importlib.import_module(module_path)
        except ModuleNotFoundError:
            logger.warning("App %r enabled but %s not importable", name, module_path)
            continue
        register_fn = getattr(app_api, "register", None)
        if register_fn is None:
            logger.warning("%s has no register(app, prefix) entrypoint", module_path)
            continue
        register_fn(app, prefix=prefix)
        logger.info("Registered routers from %s", module_path)

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
