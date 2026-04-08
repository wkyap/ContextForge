"""Connectors API — list available drivers, start/stop/inspect instances."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from contextforge.connectors.config_repo import ConnectorConfig, ConnectorConfigRepo
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
