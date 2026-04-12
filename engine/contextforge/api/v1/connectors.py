"""Connectors API — list available drivers, start/stop/inspect instances."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from contextforge.connectors.config_repo import ConnectorConfig, ConnectorConfigRepo
from contextforge.connectors.dlq import DLQRepository
from contextforge.connectors.registry import get_connector_registry

router = APIRouter(prefix="/connectors")


class StartRequest(BaseModel):
    name: str
    source_kind: str
    config: dict[str, Any] = {}
    sink: str | None = None


class ConfigBody(BaseModel):
    name: str
    source_kind: str
    config: dict[str, Any] = {}
    sink: str | None = None
    enabled: bool = True
    description: str | None = None


@router.get("/drivers")
async def list_drivers() -> dict[str, Any]:
    """List the source_kinds for which a driver is registered."""
    return {"drivers": get_connector_registry().list_kinds()}


@router.get("")
async def list_running(request: Request) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    return {"running": supervisor.list()}


@router.get("/sinks")
async def list_sinks(request: Request) -> dict[str, Any]:
    """List sink aliases registered for per-connector overrides."""
    return {"sinks": request.app.state.connector_supervisor.list_sinks()}


@router.post("/start")
async def start_connector(request: Request, body: StartRequest) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    try:
        connector = await supervisor.start(
            body.name, body.source_kind, body.config, sink_name=body.sink
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start: {exc}") from exc
    return {"name": connector.name, "health": connector.health().__dict__}


# ── Persisted configs ─────────────────────────────────────────────────────────


def _repo(request: Request) -> ConnectorConfigRepo:
    return ConnectorConfigRepo(request.app.state.postgres)


@router.get("/configs")
async def list_configs(request: Request) -> dict[str, Any]:
    cfgs = await _repo(request).list_all()
    return {"configs": [c.to_dict() for c in cfgs]}


@router.get("/configs/{name}")
async def get_config(request: Request, name: str) -> dict[str, Any]:
    cfg = await _repo(request).get(name)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Config {name!r} not found")
    return cfg.to_dict()


@router.post("/configs")
async def upsert_config(request: Request, body: ConfigBody) -> dict[str, Any]:
    cfg = ConnectorConfig(
        name=body.name,
        source_kind=body.source_kind,
        config=body.config,
        sink=body.sink,
        enabled=body.enabled,
        description=body.description,
    )
    await _repo(request).upsert(cfg)
    return cfg.to_dict()


@router.delete("/configs/{name}")
async def delete_config(request: Request, name: str) -> dict[str, Any]:
    deleted = await _repo(request).delete(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config {name!r} not found")
    return {"name": name, "deleted": True}


@router.post("/configs/{name}/start")
async def start_config(request: Request, name: str) -> dict[str, Any]:
    cfg = await _repo(request).get(name)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"Config {name!r} not found")
    supervisor = request.app.state.connector_supervisor
    try:
        connector = await supervisor.start(
            cfg.name, cfg.source_kind, cfg.config, sink_name=cfg.sink
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"name": connector.name, "health": connector.health().__dict__}


@router.post("/{name}/stop")
async def stop_connector(request: Request, name: str) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    try:
        await supervisor.stop(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"name": name, "stopped": True}


@router.get("/{name}")
async def get_connector(request: Request, name: str) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    connector = supervisor.get(name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector {name!r} not running")
    return {
        "name": connector.name,
        "source_kind": connector.source_kind,
        "config": connector.config,
        "health": connector.health().__dict__,
    }


# ── Dead-letter queue ────────────────────────────────────────────────────────


def _dlq(request: Request) -> DLQRepository:
    dlq = getattr(request.app.state, "connector_dlq", None)
    if dlq is None:
        raise HTTPException(status_code=503, detail="DLQ not configured")
    return dlq  # type: ignore[no-any-return]


@router.get("/dlq/entries")
async def list_dlq_entries(
    request: Request,
    connector_name: str | None = None,
    status: str = "pending",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List dead-letter rows, newest first. Default filter is ``status=pending``."""
    entries = await _dlq(request).list_entries(
        connector_name=connector_name,
        status=status if status != "all" else None,
        limit=limit,
        offset=offset,
    )
    return {
        "total_pending": await _dlq(request).count(connector_name=connector_name),
        "entries": [
            {
                "id": e.id,
                "connector_name": e.connector_name,
                "sink_name": e.sink_name,
                "source": e.source,
                "payload": e.payload,
                "metadata": e.metadata,
                "error": e.error,
                "record_ts": e.record_ts,
                "failed_at": e.failed_at,
                "status": e.status,
                "replayed_at": e.replayed_at,
            }
            for e in entries
        ],
    }


@router.post("/dlq/entries/{entry_id}/replay")
async def replay_dlq_entry(request: Request, entry_id: int) -> dict[str, Any]:
    """Re-write a dead-letter row to the same sink it originally targeted.

    Marks the row ``replayed`` on success or leaves it ``pending`` on failure.
    """
    dlq = _dlq(request)
    entries = await dlq.list_entries(status=None, limit=1, offset=0)
    target = next((e for e in entries if e.id == entry_id), None)
    if target is None:
        # Fall back to scanning more pages — small DLQs are fine but be defensive.
        page = 0
        while target is None:
            page += 1
            if page > 50:
                raise HTTPException(status_code=404, detail="DLQ entry not found")
            batch = await dlq.list_entries(status=None, limit=100, offset=page * 100)
            if not batch:
                raise HTTPException(status_code=404, detail="DLQ entry not found")
            target = next((e for e in batch if e.id == entry_id), None)

    supervisor = request.app.state.connector_supervisor
    sink = None
    if target.sink_name and target.sink_name in supervisor._sinks_by_name:  # noqa: SLF001
        sink = supervisor._sinks_by_name[target.sink_name]  # noqa: SLF001
    else:
        sink = supervisor._sink  # noqa: SLF001

    from contextforge.connectors.base import Record

    record = Record(
        payload=target.payload,
        source=target.source or target.connector_name,
        timestamp=target.record_ts or 0.0,
        metadata=target.metadata,
    )
    try:
        await sink.write(record)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Replay failed: {exc}") from exc

    await dlq.mark_status(entry_id, "replayed")
    return {"id": entry_id, "status": "replayed"}


@router.post("/dlq/entries/{entry_id}/ignore")
async def ignore_dlq_entry(request: Request, entry_id: int) -> dict[str, Any]:
    """Mark a DLQ row as not-recoverable."""
    await _dlq(request).mark_status(entry_id, "ignored")
    return {"id": entry_id, "status": "ignored"}
