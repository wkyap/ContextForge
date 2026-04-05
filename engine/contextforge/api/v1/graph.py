"""Graph API — stub (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/graph")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 2"})


@router.get("/entities")
async def list_entities() -> JSONResponse:
    return _501


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str) -> JSONResponse:
    return _501
