"""Admin API — audit log, config, and data seeding."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query

from contextforge.api.deps import Neo4jDep, PostgresDep, SettingsDep

router = APIRouter(prefix="/admin")


@router.get("/audit-log")
async def list_audit_log(
    postgres: PostgresDep,
    user_id: str | None = Query(None, description="Filter by user_id"),
    action_type: str | None = Query(None, description="Filter by action_type"),
    resource_type: str | None = Query(None, description="Filter by resource_type"),
    result: str | None = Query(None, pattern="^(success|failure|escalated_to_human)$"),
    since: datetime | None = Query(None, description="Only entries at/after this timestamp"),
    until: datetime | None = Query(None, description="Only entries before this timestamp"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """Query the audit log with optional filters. Newest entries first."""
    conditions: list[str] = ["1=1"]
    params: list[Any] = []
    idx = 1

    if user_id:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1
    if action_type:
        conditions.append(f"action_type = ${idx}")
        params.append(action_type)
        idx += 1
    if resource_type:
        conditions.append(f"resource_type = ${idx}")
        params.append(resource_type)
        idx += 1
    if result:
        conditions.append(f"result = ${idx}")
        params.append(result)
        idx += 1
    if since:
        conditions.append(f"timestamp >= ${idx}")
        params.append(since)
        idx += 1
    if until:
        conditions.append(f"timestamp < ${idx}")
        params.append(until)
        idx += 1

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    rows = await postgres.fetch(
        f"""
        SELECT id, timestamp, user_id, action_type, resource_type, resource_id,
               change_details, result, reason, ip_address, correlation_id
        FROM audit_log
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    total_row = await postgres.fetchrow(
        f"SELECT COUNT(*) AS n FROM audit_log WHERE {where}",
        *params[:-2],
    )
    return {
        "total": int(total_row["n"]) if total_row else 0,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "entries": [dict(r) for r in rows],
    }


@router.get("/config")
async def get_config(settings: SettingsDep) -> dict[str, Any]:
    """Return non-secret runtime configuration. Secrets are redacted."""
    return {
        "env": settings.env,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "auth_disabled": settings.auth_disabled,
        "postgres": {
            "host": settings.postgres_host,
            "port": settings.postgres_port,
            "db": settings.postgres_db,
            "user": settings.postgres_user,
        },
        "timescale": {
            "host": settings.timescale_host,
            "port": settings.timescale_port,
            "db": settings.timescale_db,
        },
        "neo4j": {"uri": settings.neo4j_uri, "user": settings.neo4j_user},
        "qdrant": {"host": settings.qdrant_host, "port": settings.qdrant_port},
        "redis": {"host": settings.redis_host, "port": settings.redis_port},
        "litellm": {"base_url": settings.litellm_base_url},
    }


@router.post("/seed/careerforge")
async def seed_careerforge(postgres: PostgresDep, neo4j: Neo4jDep) -> dict[str, Any]:
    """Seed CareerForge synthetic data + SSG taxonomy. Dev only."""
    from contextforge.data.seed.careerforge_synthetic import seed_careerforge_data
    from contextforge.ingestion.ssg_taxonomy import load_ssg_taxonomy

    taxonomy_result = await load_ssg_taxonomy(neo4j, postgres)
    data_counts = await seed_careerforge_data(postgres)

    return {
        "synthetic_data": data_counts,
        "ssg_taxonomy": {
            "skills_created": taxonomy_result.entities_created,
            "relationships_created": taxonomy_result.relationships_created,
            "errors": taxonomy_result.errors[:5],
        },
    }
