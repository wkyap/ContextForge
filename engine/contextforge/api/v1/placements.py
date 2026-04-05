"""Placements API — record and track employment outcomes."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/placements")


class PlacementCreate(BaseModel):
    trainee_id: str
    employer_id: str
    opening_id: str | None = None
    programme_id: str | None = None
    placement_type: str = Field(..., pattern="^(full-time|part-time|contract)$")
    source: str = Field(..., pattern="^(lhub-matched|self-sourced)$")
    start_date: str | None = None
    salary: float | None = None


class PlacementUpdate(BaseModel):
    status: str | None = None
    verified_by: str | None = None


@router.get("")
async def list_placements(
    postgres: PostgresDep,
    status: str | None = None,
    programme_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List placements with optional filters."""
    conditions = []
    params: list = []
    idx = 1

    if status:
        conditions.append(f"p.status = ${idx}")
        params.append(status)
        idx += 1
    if programme_id:
        conditions.append(f"p.programme_id::text = ${idx}")
        params.append(programme_id)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.extend([limit, offset])

    rows = await postgres.fetch(
        f"""SELECT p.id, p.placement_type, p.source, p.start_date,
           p.status, p.created_at, t.name as trainee_name,
           t.trainee_code, e.company_name
           FROM placements p
           JOIN trainees t ON p.trainee_id = t.id
           JOIN employers e ON p.employer_id = e.id
           {where}
           ORDER BY p.created_at DESC LIMIT ${idx} OFFSET ${idx+1}""",
        params,
    )

    return {"placements": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_placement(body: PlacementCreate, postgres: PostgresDep) -> dict:
    """Record a new placement."""
    placement_id = str(uuid.uuid4())

    await postgres.execute(
        """INSERT INTO placements (id, trainee_id, employer_id, opening_id,
           programme_id, placement_type, source, start_date, salary)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
        [
            placement_id, body.trainee_id, body.employer_id,
            body.opening_id, body.programme_id, body.placement_type,
            body.source, body.start_date, body.salary,
        ],
    )

    # Update trainee status to 'placed'
    await postgres.execute(
        "UPDATE trainees SET status = 'placed', updated_at = now() WHERE id = $1",
        [body.trainee_id],
    )

    return {"id": placement_id, "status": "pending"}


@router.patch("/{placement_id}")
async def update_placement(
    placement_id: str,
    body: PlacementUpdate,
    postgres: PostgresDep,
) -> dict:
    """Update placement status (verify/reject)."""
    updates = []
    params = []
    idx = 1

    if body.status:
        updates.append(f"status = ${idx}")
        params.append(body.status)
        idx += 1
        if body.status == "verified":
            updates.append(f"verified_at = now()")
    if body.verified_by:
        updates.append(f"verified_by = ${idx}")
        params.append(body.verified_by)
        idx += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    params.append(placement_id)
    await postgres.execute(
        f"UPDATE placements SET {', '.join(updates)} WHERE id::text = ${idx}",
        params,
    )

    return {"updated": True}
