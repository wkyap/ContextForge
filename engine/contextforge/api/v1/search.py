"""Search API — stub (Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/search")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 3"})


@router.post("")
async def semantic_search() -> JSONResponse:
    return _501
