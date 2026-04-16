"""Timeseries API — query and ingest telemetry data from TimescaleDB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from contextforge.api.deps import TimescaleDep

router = APIRouter(prefix="/timeseries")


# ── Models ───────────────────────────────────────────────────────────────────

class TelemetryPoint(BaseModel):
    time: datetime
    entity_id: str
    channel_id: str = "api"
    parameter: str
    value: float
    unit: str
    quality: str = "valid"


class TelemetryBatch(BaseModel):
    points: list[TelemetryPoint] = Field(..., min_length=1, max_length=1000)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/query")
async def query_timeseries(
    timescale: TimescaleDep,
    entity_id: str = Query(...),
    parameter: str = Query(...),
    start: str | None = Query(None, description="ISO 8601 start time"),
    end: str | None = Query(None, description="ISO 8601 end time"),
    bucket: str = Query("5 minutes", description="Aggregation bucket size"),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start_dt = datetime.fromisoformat(start) if start else now - timedelta(hours=24)
    end_dt = datetime.fromisoformat(end) if end else now

    records = await timescale.query_aggregated(
        entity_id, parameter, start=start_dt, end=end_dt, bucket=bucket,
    )
    return {
        "entity_id": entity_id,
        "parameter": parameter,
        "bucket": bucket,
        "count": len(records),
        "data": [dict(r) for r in records],
    }


@router.get("/latest")
async def get_latest(
    timescale: TimescaleDep,
    entity_id: str = Query(...),
    parameter: str = Query(...),
) -> dict[str, Any]:
    record = await timescale.query_latest(entity_id, parameter)
    if not record:
        return {"entity_id": entity_id, "parameter": parameter, "data": None}
    return {
        "entity_id": entity_id,
        "parameter": parameter,
        "data": dict(record),
    }


@router.get("/parameters")
async def list_parameters(
    timescale: TimescaleDep,
    entity_id: str = Query(...),
) -> dict[str, Any]:
    records = await timescale.get_entity_parameters(entity_id)
    return {
        "entity_id": entity_id,
        "count": len(records),
        "parameters": [dict(r) for r in records],
    }


@router.get("/trend")
async def trend_analysis(
    timescale: TimescaleDep,
    entity_id: str = Query(...),
    parameter: str = Query(...),
    start: str | None = Query(None),
    end: str | None = Query(None),
    bucket: str = Query("1 hour"),
) -> dict[str, Any]:
    now = datetime.now(UTC)
    start_dt = datetime.fromisoformat(start) if start else now - timedelta(days=7)
    end_dt = datetime.fromisoformat(end) if end else now

    records = await timescale.trend_analysis(
        entity_id, parameter, start=start_dt, end=end_dt, bucket=bucket,
    )
    return {
        "entity_id": entity_id,
        "parameter": parameter,
        "bucket": bucket,
        "count": len(records),
        "data": [dict(r) for r in records],
    }


@router.post("/ingest")
async def ingest_telemetry(body: TelemetryBatch, timescale: TimescaleDep) -> dict[str, Any]:
    rows = [
        (p.time, p.entity_id, p.channel_id, p.parameter, p.value, p.unit, p.quality)
        for p in body.points
    ]
    await timescale.insert_telemetry_batch(rows)
    return {"ingested": len(rows)}


@router.get("/range")
async def query_raw(
    timescale: TimescaleDep,
    entity_id: str = Query(...),
    parameter: str = Query(...),
    start: str = Query(..., description="ISO 8601 start time"),
    end: str = Query(..., description="ISO 8601 end time"),
) -> dict[str, Any]:
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    records = await timescale.query_range(
        entity_id, parameter, start=start_dt, end=end_dt,
    )
    return {
        "entity_id": entity_id,
        "parameter": parameter,
        "count": len(records),
        "data": [dict(r) for r in records],
    }
