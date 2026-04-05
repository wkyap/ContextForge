"""Pipelines API — stub (Phase 5)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/pipelines")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 5"})


@router.get("")
async def list_pipelines() -> JSONResponse:
    return _501


@router.post("")
async def create_pipeline() -> JSONResponse:
    return _501
