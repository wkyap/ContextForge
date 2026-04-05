"""GET /api/v1/health — aggregate health check for all backing services."""

from __future__ import annotations

from fastapi import APIRouter

from contextforge.api.deps import (
    Neo4jDep,
    PostgresDep,
    QdrantDep,
    RedisDep,
    TimescaleDep,
)

router = APIRouter()


@router.get("/health")
async def health_check(
    postgres: PostgresDep,
    timescale: TimescaleDep,
    neo4j: Neo4jDep,
    qdrant: QdrantDep,
    redis: RedisDep,
) -> dict:
    checks = {
        "postgres": await postgres.health_check(),
        "timescale": await timescale.health_check(),
        "neo4j": await neo4j.health_check(),
        "qdrant": await qdrant.health_check(),
        "redis": await redis.health_check(),
    }
    all_ok = all(checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "services": checks,
    }
