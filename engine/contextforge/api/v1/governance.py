"""Governance API — stub (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/governance")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 8"})


@router.get("/proposals")
async def list_proposals() -> JSONResponse:
    return _501


@router.get("/autonomy-levels")
async def list_autonomy_levels() -> JSONResponse:
    return _501
