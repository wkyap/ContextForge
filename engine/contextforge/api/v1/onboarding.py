"""Onboarding API — stub (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/onboarding")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 8"})


@router.post("/domain")
async def onboard_domain() -> JSONResponse:
    return _501
