"""Timeseries API — stub (Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/timeseries")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 2"})


@router.get("/query")
async def query_timeseries() -> JSONResponse:
    return _501
