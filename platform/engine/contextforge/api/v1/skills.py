"""Skills API — list, retrieve, and search skills from the registry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from contextforge.api.deps import QdrantDep, SettingsDep
from contextforge.knowledge.embedding_service import EmbeddingService
from contextforge.skills.search import search_skills

router = APIRouter(prefix="/skills")


@router.get("")
async def list_skills(
    request: Request,
    domain: str | None = Query(None),
    type: str | None = Query(None, alias="type"),
) -> dict[str, Any]:
    registry = request.app.state.skill_registry
    if domain:
        skills = registry.list_by_domain(domain)
    elif type:
        skills = registry.list_by_type(type)
    else:
        skills = registry.list_all()
    return {
        "count": len(skills),
        "skills": [
            {
                "name": s.name,
                "type": s.type,
                "domain": s.domain,
                "version": s.version,
                "description": s.description,
                "author": s.author,
                "tags": s.tags,
            }
            for s in skills
        ],
    }


@router.get("/{name}")
async def get_skill(name: str, request: Request) -> dict[str, Any]:
    registry = request.app.state.skill_registry
    skill = registry.get(name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {
        "name": skill.name,
        "type": skill.type,
        "domain": skill.domain,
        "version": skill.version,
        "description": skill.description,
        "author": skill.author,
        "tags": skill.tags,
        "metadata": skill.metadata,
        "body": skill.body,
    }


@router.get("/search")
async def search_skills_endpoint(
    qdrant: QdrantDep,
    settings: SettingsDep,
    q: str = Query(..., min_length=1, description="Semantic search query"),
    domain: str | None = Query(None),
    skill_type: str | None = Query(None, alias="type"),
    limit: int = Query(5, ge=1, le=50),
) -> dict[str, Any]:
    """Semantic search for skills using vector similarity."""
    embeddings = EmbeddingService(settings)
    query_vector = await embeddings.embed(q)
    results = await search_skills(
        qdrant, query_vector, limit=limit, domain=domain, skill_type=skill_type,
    )
    return {"query": q, "count": len(results), "results": results}
