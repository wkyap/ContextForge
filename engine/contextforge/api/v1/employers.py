"""Employers API — CRUD for employer partners in the placement network."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from contextforge.api.deps import PostgresDep, Neo4jDep

router = APIRouter(prefix="/employers")


class EmployerCreate(BaseModel):
    company_name: str = Field(..., max_length=300)
    uen: str | None = None
    sector: str | None = None
    size: str | None = None
    locations: list[str] = []
    partnership_tier: str = "new"
    contact_email: str | None = None


@router.get("")
async def list_employers(
    postgres: PostgresDep,
    sector: str | None = None,
    tier: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """List employer partners."""
    conditions = []
    params: list = []
    idx = 1

    if sector:
        conditions.append(f"sector = ${idx}")
        params.append(sector)
        idx += 1
    if tier:
        conditions.append(f"partnership_tier = ${idx}")
        params.append(tier)
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    count_row = await postgres.fetch_one(
        f"SELECT count(*) as cnt FROM employers {where}", params
    )
    total = count_row["cnt"] if count_row else 0

    params.extend([limit, offset])
    rows = await postgres.fetch(
        f"SELECT id, company_name, uen, sector, size, locations, partnership_tier "
        f"FROM employers {where} ORDER BY company_name LIMIT ${idx} OFFSET ${idx+1}",
        params,
    )

    return {"total": total, "employers": [dict(r) for r in rows]}


@router.get("/{employer_id}")
async def get_employer(employer_id: str, postgres: PostgresDep) -> dict:
    """Get employer by ID or UEN."""
    row = await postgres.fetch_one(
        "SELECT * FROM employers WHERE id::text = $1 OR uen = $1",
        [employer_id],
    )
    if not row:
        raise HTTPException(status_code=404, detail="Employer not found")
    return dict(row)


@router.post("", status_code=201)
async def create_employer(
    body: EmployerCreate,
    postgres: PostgresDep,
    neo4j: Neo4jDep,
) -> dict:
    """Register a new employer partner."""
    employer_id = str(uuid.uuid4())

    await postgres.execute(
        """INSERT INTO employers (id, company_name, uen, sector, size,
           locations, partnership_tier, contact_email)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
        [
            employer_id, body.company_name, body.uen, body.sector,
            body.size, body.locations, body.partnership_tier,
            body.contact_email,
        ],
    )

    neo4j_id = f"employer:{body.uen or employer_id}"
    await neo4j.execute_write(
        """CREATE (e:Employer:Entity {
            id: $id, company_name: $name, uen: $uen,
            sector: $sector, size: $size, partnership_tier: $tier,
            _is_current: true, _created_at: datetime(),
            _type: 'Employer', _version: 1
        }) RETURN e.id AS id""",
        {
            "id": neo4j_id, "name": body.company_name,
            "uen": body.uen or "", "sector": body.sector or "",
            "size": body.size or "", "tier": body.partnership_tier,
        },
    )

    await postgres.execute(
        "UPDATE employers SET neo4j_entity_id = $1 WHERE id = $2",
        [neo4j_id, employer_id],
    )

    return {"id": employer_id, "company_name": body.company_name}
