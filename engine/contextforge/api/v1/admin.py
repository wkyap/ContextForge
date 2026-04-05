"""Admin API — audit log, config, and data seeding."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from contextforge.api.deps import PostgresDep, Neo4jDep

router = APIRouter(prefix="/admin")

_501 = JSONResponse(status_code=501, content={"detail": "Not implemented — coming in Phase 9"})


@router.get("/audit-log")
async def list_audit_log() -> JSONResponse:
    return _501


@router.get("/config")
async def get_config() -> JSONResponse:
    return _501


@router.post("/seed/careerforge")
async def seed_careerforge(postgres: PostgresDep, neo4j: Neo4jDep) -> dict:
    """Seed CareerForge synthetic data + SSG taxonomy. Dev only."""
    from contextforge.data.seed.careerforge_synthetic import seed_careerforge_data
    from contextforge.ingestion.ssg_taxonomy import load_ssg_taxonomy

    taxonomy_result = await load_ssg_taxonomy(neo4j, postgres)
    data_counts = await seed_careerforge_data(postgres)

    return {
        "synthetic_data": data_counts,
        "ssg_taxonomy": {
            "skills_created": taxonomy_result.entities_created,
            "relationships_created": taxonomy_result.relationships_created,
            "errors": taxonomy_result.errors[:5],
        },
    }
