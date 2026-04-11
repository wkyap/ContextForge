"""Job Openings API — CRUD + AI matching for employer vacancies."""

from __future__ import annotations

import uuid

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/openings")


class OpeningCreate(BaseModel):
    employer_id: str
    role_title: str = Field(..., max_length=300)
    description: str | None = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    experience_years: int = 0
    salary_min: float | None = None
    salary_max: float | None = None
    work_arrangement: str | None = None


@router.get("")
async def list_openings(
    postgres: PostgresDep,
    status: str = "open",
    sector: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List job openings."""
    rows = await postgres.fetch(
        """SELECT o.id, o.role_title, o.required_skills, o.preferred_skills,
           o.experience_years, o.salary_min, o.salary_max, o.work_arrangement,
           o.status, o.posted_at, e.company_name, e.sector
           FROM job_openings o
           JOIN employers e ON o.employer_id = e.id
           WHERE o.status = $1
           ORDER BY o.posted_at DESC LIMIT $2 OFFSET $3""",
        [status, limit, offset],
    )
    return {"openings": [dict(r) for r in rows]}


@router.get("/{opening_id}")
async def get_opening(opening_id: str, postgres: PostgresDep) -> dict[str, Any]:
    """Get a single job opening."""
    row = await postgres.fetch_one(
        """SELECT o.*, e.company_name, e.sector as employer_sector
           FROM job_openings o
           JOIN employers e ON o.employer_id = e.id
           WHERE o.id::text = $1""",
        [opening_id],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Opening not found")
    return dict(row)


@router.post("", status_code=201)
async def create_opening(body: OpeningCreate, postgres: PostgresDep) -> dict[str, Any]:
    """Post a new job opening."""
    opening_id = str(uuid.uuid4())

    await postgres.execute(
        """INSERT INTO job_openings (id, employer_id, role_title, description,
           required_skills, preferred_skills, experience_years,
           salary_min, salary_max, work_arrangement)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        [
            opening_id, body.employer_id, body.role_title, body.description,
            body.required_skills, body.preferred_skills, body.experience_years,
            body.salary_min, body.salary_max, body.work_arrangement,
        ],
    )

    return {"id": opening_id, "role_title": body.role_title, "status": "open"}


@router.get("/{opening_id}/matches")
async def get_opening_matches(
    opening_id: str,
    postgres: PostgresDep,
    limit: int = 20,
) -> dict[str, Any]:
    """Get AI-ranked trainee matches for a job opening."""
    # Return cached matching results if they exist
    rows = await postgres.fetch(
        """SELECT mr.trainee_id, mr.composite_score, mr.skill_coverage,
           mr.score_breakdown, mr.explanation, t.name, t.trainee_code,
           t.education_level, t.years_experience, t.status
           FROM matching_results mr
           JOIN trainees t ON mr.trainee_id = t.id
           WHERE mr.target_type = 'job_opening' AND mr.target_id::text = $1
           ORDER BY mr.composite_score DESC LIMIT $2""",
        [opening_id, limit],
    )

    return {
        "opening_id": opening_id,
        "matches": [dict(r) for r in rows],
        "total": len(rows),
    }
