"""CareerForge API — routers discovered by the platform at startup.

Platform main.py imports ``apps.<name>.api`` for each entry in
``CONTEXTFORGE_APPS_ENABLED`` and calls ``register(app, prefix)`` below.
"""

from __future__ import annotations

from fastapi import FastAPI

from apps.careerforge.api import (
    admin,
    courses,
    employers,
    openings,
    placements,
    reports,
    trainees,
)


def register(app: FastAPI, *, prefix: str) -> None:
    """Mount every CareerForge router onto the FastAPI app."""
    app.include_router(admin.router, prefix=prefix, tags=["careerforge", "admin"])
    app.include_router(trainees.router, prefix=prefix, tags=["careerforge", "trainees"])
    app.include_router(courses.router, prefix=prefix, tags=["careerforge", "courses"])
    app.include_router(employers.router, prefix=prefix, tags=["careerforge", "employers"])
    app.include_router(openings.router, prefix=prefix, tags=["careerforge", "openings"])
    app.include_router(placements.router, prefix=prefix, tags=["careerforge", "placements"])
    app.include_router(reports.router, prefix=prefix, tags=["careerforge", "reports"])
