"""FastAPI dependency injection — singletons for DB clients and settings."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from contextforge.config import Settings, get_settings
from contextforge.db.neo4j import Neo4jClient
from contextforge.db.postgres import PostgresClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.redis import RedisClient
from contextforge.db.timescale import TimescaleClient

# ── Settings ──────────────────────────────────────────────────────────────────

SettingsDep = Annotated[Settings, Depends(get_settings)]


# ── DB clients (stored on app.state during lifespan) ─────────────────────────

def _get_postgres(request: Request) -> PostgresClient:
    return cast(PostgresClient, request.app.state.postgres)


def _get_timescale(request: Request) -> TimescaleClient:
    return cast(TimescaleClient, request.app.state.timescale)


def _get_neo4j(request: Request) -> Neo4jClient:
    return cast(Neo4jClient, request.app.state.neo4j)


def _get_qdrant(request: Request) -> QdrantClient:
    return cast(QdrantClient, request.app.state.qdrant)


def _get_redis(request: Request) -> RedisClient:
    return cast(RedisClient, request.app.state.redis)


PostgresDep = Annotated[PostgresClient, Depends(_get_postgres)]
TimescaleDep = Annotated[TimescaleClient, Depends(_get_timescale)]
Neo4jDep = Annotated[Neo4jClient, Depends(_get_neo4j)]
QdrantDep = Annotated[QdrantClient, Depends(_get_qdrant)]
RedisDep = Annotated[RedisClient, Depends(_get_redis)]
