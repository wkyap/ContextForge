"""Pipelines API — manage data ingestion pipelines."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep, RedisDep

router = APIRouter(prefix="/pipelines")


# ── Models ───────────────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    name: str = Field(..., max_length=200)
    domain: str | None = None
    type: str = Field(..., pattern="^(api|stream|document|batch)$")
    config: dict[str, Any] = {}
    schedule_cron: str | None = None
    description: str = ""


class PipelineUpdate(BaseModel):
    name: str | None = None
    config: dict[str, Any] | None = None
    schedule_cron: str | None = None
    enabled: bool | None = None
    description: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_pipelines(
    postgres: PostgresDep,
    domain: str | None = Query(None),
    enabled: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    conditions = ["1=1"]
    params: list[Any] = []
    idx = 1

    if domain:
        conditions.append(f"domain = ${idx}")
        params.append(domain)
        idx += 1
    if enabled is not None:
        conditions.append(f"enabled = ${idx}")
        params.append(enabled)
        idx += 1

    params.append(limit)
    rows = await postgres.fetch(
        f"""
        SELECT id, name, description, type, domain, enabled, schedule_cron,
               last_run_at, last_run_status, error_count_24h,
               records_processed_24h, created_at
        FROM pipelines
        WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC
        LIMIT ${idx}
        """,
        *params,
    )
    return {"count": len(rows), "pipelines": [dict(r) for r in rows]}


@router.post("")
async def create_pipeline(body: PipelineCreate, postgres: PostgresDep) -> dict[str, Any]:
    pipeline_id = str(uuid.uuid4())
    await postgres.execute(
        """
        INSERT INTO pipelines (id, name, description, type, domain, config, schedule_cron)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        """,
        pipeline_id, body.name, body.description, body.type,
        body.domain, json.dumps(body.config), body.schedule_cron,
    )
    return {"id": pipeline_id, "name": body.name, "status": "created"}


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str, postgres: PostgresDep) -> dict[str, Any]:
    row = await postgres.fetchrow(
        "SELECT * FROM pipelines WHERE id = $1", pipeline_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return dict(row)


@router.put("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    postgres: PostgresDep,
) -> dict[str, Any]:
    existing = await postgres.fetchrow(
        "SELECT id FROM pipelines WHERE id = $1", pipeline_id
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    updates = []
    params: list[Any] = [pipeline_id]
    idx = 2

    for field_name, value in body.model_dump(exclude_unset=True).items():
        if field_name == "config" and value is not None:
            updates.append(f"config = ${idx}::jsonb")
            params.append(json.dumps(value))
        else:
            updates.append(f"{field_name} = ${idx}")
            params.append(value)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append(f"updated_at = ${idx}")
    params.append(datetime.now(UTC))

    await postgres.execute(
        f"UPDATE pipelines SET {', '.join(updates)} WHERE id = $1",
        *params,
    )
    return {"id": pipeline_id, "status": "updated"}


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, postgres: PostgresDep) -> dict[str, Any]:
    result = await postgres.execute(
        "DELETE FROM pipelines WHERE id = $1", pipeline_id
    )
    if "DELETE 0" in result:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"id": pipeline_id, "status": "deleted"}


@router.post("/{pipeline_id}/trigger")
async def trigger_pipeline(
    pipeline_id: str,
    postgres: PostgresDep,
    redis: RedisDep,
) -> dict[str, Any]:
    row = await postgres.fetchrow(
        "SELECT id, name, enabled FROM pipelines WHERE id = $1", pipeline_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not row["enabled"]:
        raise HTTPException(status_code=400, detail="Pipeline is disabled")

    run_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    await postgres.execute(
        """
        INSERT INTO pipeline_runs (id, pipeline_id, status, started_at)
        VALUES ($1, $2, 'running', $3)
        """,
        run_id, pipeline_id, now,
    )

    await postgres.execute(
        "UPDATE pipelines SET last_run_status = 'running', last_run_at = $2 WHERE id = $1",
        pipeline_id, now,
    )

    await redis.publish("pipelines:trigger", {
        "run_id": run_id,
        "pipeline_id": pipeline_id,
    })

    return {"run_id": run_id, "pipeline_id": pipeline_id, "status": "running"}


@router.get("/{pipeline_id}/runs")
async def list_pipeline_runs(
    pipeline_id: str,
    postgres: PostgresDep,
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    rows = await postgres.fetch(
        """
        SELECT id, status, started_at, completed_at, records_processed,
               error_count, error_message
        FROM pipeline_runs
        WHERE pipeline_id = $1
        ORDER BY started_at DESC
        LIMIT $2
        """,
        pipeline_id, limit,
    )
    return {"pipeline_id": pipeline_id, "count": len(rows), "runs": [dict(r) for r in rows]}
