"""Skills API — list and retrieve skills from the registry."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/skills")


@router.get("")
async def list_skills(
    request: Request,
    domain: str | None = Query(None),
    type: str | None = Query(None, alias="type"),
) -> dict:
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
async def get_skill(name: str, request: Request) -> dict:
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
