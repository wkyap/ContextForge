"""Courses API — CRUD for training courses in career placement programmes."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from contextforge.api.deps import PostgresDep, Neo4jDep

router = APIRouter(prefix="/courses")


# ── Models ───────────────────────────────────────────────────────────────────

class CourseCreate(BaseModel):
    course_code: str = Field(..., max_length=50)
    title: str = Field(..., max_length=300)
    provider: str = "NTUC LearningHub"
    sector: str | None = None
    duration_weeks: int | None = None
    mode: str | None = None
    skills_taught: list[str] = []
    prerequisites: list[str] = []
    ssg_course_code: str | None = None
    capacity: int | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_courses(
    postgres: PostgresDep,
    sector: str | None = None,
    mode: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List courses with optional filters."""
    conditions = []
    params: list = []
    idx = 1

    if sector:
        conditions.append(f"sector = ${idx}")
        params.append(sector)
        idx += 1
    if mode:
        conditions.append(f"mode = ${idx}")
        params.append(mode)
        idx += 1

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    count_row = await postgres.fetch_one(
        f"SELECT count(*) as cnt FROM courses {where}", params
    )
    total = count_row["cnt"] if count_row else 0

    params.extend([limit, offset])
    rows = await postgres.fetch(
        f"SELECT id, course_code, title, provider, sector, duration_weeks, mode, "
        f"skills_taught, ssg_course_code, capacity, current_enrolment "
        f"FROM courses {where} ORDER BY title LIMIT ${idx} OFFSET ${idx+1}",
        params,
    )

    return {"total": total, "courses": [dict(r) for r in rows]}


@router.get("/{course_id}")
async def get_course(course_id: str, postgres: PostgresDep) -> dict:
    """Get a single course by ID or course_code."""
    row = await postgres.fetch_one(
        "SELECT * FROM courses WHERE id::text = $1 OR course_code = $1",
        [course_id],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Course not found")
    return dict(row)


@router.post("", status_code=201)
async def create_course(
    body: CourseCreate,
    postgres: PostgresDep,
    neo4j: Neo4jDep,
) -> dict:
    """Create a new course."""
    course_id = str(uuid.uuid4())

    await postgres.execute(
        """INSERT INTO courses (id, course_code, title, provider, sector,
           duration_weeks, mode, skills_taught, prerequisites, ssg_course_code, capacity)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)""",
        [
            course_id, body.course_code, body.title, body.provider,
            body.sector, body.duration_weeks, body.mode,
            body.skills_taught, body.prerequisites,
            body.ssg_course_code, body.capacity,
        ],
    )

    neo4j_id = f"course:{body.course_code}"
    await neo4j.execute_write(
        """CREATE (c:Course:Entity {
            id: $id, course_id: $code, title: $title,
            sector: $sector, duration_weeks: $dur, mode: $mode,
            _is_current: true, _created_at: datetime(),
            _type: 'Course', _version: 1
        }) RETURN c.id AS id""",
        {
            "id": neo4j_id, "code": body.course_code, "title": body.title,
            "sector": body.sector or "", "dur": body.duration_weeks or 0,
            "mode": body.mode or "",
        },
    )

    await postgres.execute(
        "UPDATE courses SET neo4j_entity_id = $1 WHERE id = $2",
        [neo4j_id, course_id],
    )

    return {"id": course_id, "course_code": body.course_code}
