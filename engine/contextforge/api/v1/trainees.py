"""Trainees API — CRUD + AI recommendations for career placement trainees."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from contextforge.api.deps import PostgresDep, Neo4jDep

router = APIRouter(prefix="/trainees")


# ── Models ───────────────────────────────────────────────────────────────────

class TraineeCreate(BaseModel):
    trainee_code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    email: str | None = None
    phone_masked: str | None = None
    nric_hash: str | None = None
    education_level: str | None = None
    field_of_study: str | None = None
    years_experience: int = 0
    career_goals: list[str] = []
    preferred_sectors: list[str] = []
    preferred_locations: list[str] = []
    programme_type: str | None = None
    programme_id: str | None = None


class TraineeUpdate(BaseModel):
    status: str | None = None
    career_goals: list[str] | None = None
    preferred_sectors: list[str] | None = None
    preferred_locations: list[str] | None = None
    education_level: str | None = None
    years_experience: int | None = None


class TraineeOut(BaseModel):
    id: str
    trainee_code: str
    name: str
    email: str | None = None
    education_level: str | None = None
    field_of_study: str | None = None
    years_experience: int = 0
    career_goals: list = []
    preferred_sectors: list = []
    programme_type: str | None = None
    status: str = "applied"
    created_at: str | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def list_trainees(
    postgres: PostgresDep,
    status: str | None = None,
    programme_type: str | None = None,
    sector: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List trainees with optional filters."""
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if programme_type:
        conditions.append(f"programme_type = ${idx}")
        params.append(programme_type)
        idx += 1

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    count_row = await postgres.fetch_one(
        f"SELECT count(*) as cnt FROM trainees {where}", params
    )
    total = count_row["cnt"] if count_row else 0

    params.extend([limit, offset])
    rows = await postgres.fetch(
        f"SELECT id, trainee_code, name, email, education_level, field_of_study, "
        f"years_experience, career_goals, preferred_sectors, programme_type, status, "
        f"created_at FROM trainees {where} "
        f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}",
        params,
    )

    return {
        "total": total,
        "trainees": [dict(r) for r in rows],
    }


@router.get("/{trainee_id}")
async def get_trainee(trainee_id: str, postgres: PostgresDep) -> dict:
    """Get a single trainee by ID."""
    row = await postgres.fetch_one(
        "SELECT * FROM trainees WHERE id = $1 OR trainee_code = $1",
        [trainee_id],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Trainee not found")
    return dict(row)


@router.post("", status_code=201)
async def create_trainee(
    body: TraineeCreate,
    postgres: PostgresDep,
    neo4j: Neo4jDep,
) -> dict:
    """Create a new trainee record."""
    trainee_id = str(uuid.uuid4())

    # Insert into Postgres
    await postgres.execute(
        """INSERT INTO trainees (id, trainee_code, name, email, phone_masked,
           nric_hash, education_level, field_of_study, years_experience,
           career_goals, preferred_sectors, preferred_locations,
           programme_type, programme_id, status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'applied')""",
        [
            trainee_id, body.trainee_code, body.name, body.email,
            body.phone_masked, body.nric_hash, body.education_level,
            body.field_of_study, body.years_experience,
            body.career_goals, body.preferred_sectors,
            body.preferred_locations, body.programme_type,
            body.programme_id,
        ],
    )

    # Create Neo4j node
    neo4j_id = f"trainee:{body.trainee_code}"
    await neo4j.execute_write(
        """CREATE (t:Trainee:Entity {
            id: $id, trainee_id: $trainee_code, name: $name,
            education_level: $edu, years_experience: $exp,
            programme_type: $prog, status: 'applied',
            _is_current: true, _created_at: datetime(),
            _type: 'Trainee', _version: 1
        }) RETURN t.id AS id""",
        {
            "id": neo4j_id, "trainee_code": body.trainee_code,
            "name": body.name, "edu": body.education_level or "",
            "exp": body.years_experience, "prog": body.programme_type or "",
        },
    )

    # Link back
    await postgres.execute(
        "UPDATE trainees SET neo4j_entity_id = $1 WHERE id = $2",
        [neo4j_id, trainee_id],
    )

    return {"id": trainee_id, "trainee_code": body.trainee_code, "status": "applied"}


@router.patch("/{trainee_id}")
async def update_trainee(
    trainee_id: str,
    body: TraineeUpdate,
    postgres: PostgresDep,
) -> dict:
    """Update trainee fields."""
    updates = []
    params = []
    idx = 1

    for field_name, value in body.model_dump(exclude_none=True).items():
        updates.append(f"{field_name} = ${idx}")
        params.append(value)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(trainee_id)
    updates.append(f"updated_at = ${idx}")
    params.append(datetime.utcnow())
    idx += 1

    await postgres.execute(
        f"UPDATE trainees SET {', '.join(updates)} WHERE id = ${idx - 1} OR trainee_code = ${idx - 1}",
        params,
    )
    return {"updated": True}


@router.get("/{trainee_id}/timeline")
async def get_trainee_timeline(trainee_id: str, postgres: PostgresDep) -> dict:
    """Get trainee lifecycle timeline events."""
    events = []

    # Applications
    apps = await postgres.fetch(
        "SELECT course_id, status, match_score, created_at, reviewed_at "
        "FROM applications WHERE trainee_id = $1 ORDER BY created_at",
        [trainee_id],
    )
    for a in apps:
        events.append({"type": "application", "data": dict(a)})

    # Placements
    placements = await postgres.fetch(
        "SELECT employer_id, placement_type, source, start_date, status, created_at "
        "FROM placements WHERE trainee_id = $1 ORDER BY created_at",
        [trainee_id],
    )
    for p in placements:
        events.append({"type": "placement", "data": dict(p)})

    # Documents
    docs = await postgres.fetch(
        "SELECT document_type, verification_status, confidence, created_at "
        "FROM documents WHERE trainee_id = $1 ORDER BY created_at",
        [trainee_id],
    )
    for d in docs:
        events.append({"type": "document", "data": dict(d)})

    events.sort(key=lambda e: str(e["data"].get("created_at", "")))
    return {"trainee_id": trainee_id, "events": events}
