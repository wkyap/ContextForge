"""Connectors API — list available drivers, start/stop/inspect instances."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from contextforge.connectors.registry import get_connector_registry

router = APIRouter(prefix="/connectors")


class StartRequest(BaseModel):
    name: str
    source_kind: str
    config: dict[str, Any] = {}


@router.get("/drivers")
async def list_drivers() -> dict[str, Any]:
    """List the source_kinds for which a driver is registered."""
    return {"drivers": get_connector_registry().list_kinds()}


@router.get("")
async def list_running(request: Request) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    return {"running": supervisor.list()}


@router.post("/start")
async def start_connector(request: Request, body: StartRequest) -> dict[str, Any]:
    supervisor = request.app.state.connector_supervisor
    try:
        connector = await supervisor.start(body.name, body.source_kind, body.config)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start: {exc}") from exc
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
