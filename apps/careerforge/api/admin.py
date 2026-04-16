"""CareerForge admin — synthetic seed + SSG taxonomy loader."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from contextforge.api.deps import Neo4jDep, PostgresDep

from apps.careerforge.ingestion.ssg_taxonomy import load_ssg_taxonomy
from apps.careerforge.seed.synthetic import seed_careerforge_data

router = APIRouter(prefix="/admin")


@router.post("/seed/careerforge")
async def seed_careerforge(postgres: PostgresDep, neo4j: Neo4jDep) -> dict[str, Any]:
    """Seed CareerForge synthetic data + SSG taxonomy. Dev only."""
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
