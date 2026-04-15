"""Agent configuration CRUD — compose custom agent graphs."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/agent/configs")


# ── Models ──────────────────────────────────────────────────────────────────

class AgentConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    domain: str = "industrial"
    model_tier: str = Field("medium", pattern=r"^(small|medium|large)$")
    specialists: list[str] = Field(
        default=["retrieval", "analysis", "action"],
        description="Ordered list of specialist nodes to include",
    )
    guardrails: dict[str, bool] = Field(
        default={"pii": True, "toxicity": True, "hallucination": True},
    )
    budget_limit: float = 5.0
    max_iterations: int = 15
    is_default: bool = False


class AgentConfigUpdate(BaseModel):
    description: str | None = None
    domain: str | None = None
    model_tier: str | None = None
    specialists: list[str] | None = None
    guardrails: dict[str, bool] | None = None
    budget_limit: float | None = None
    max_iterations: int | None = None
    is_default: bool | None = None


# ── Available building blocks ───────────────────────────────────────────────

SPECIALIST_CATALOG = [
    {
        "id": "retrieval",
        "name": "Retrieval Specialist",
        "description": "Fuses results from Neo4j (KG), Qdrant (vector), and TimescaleDB",
        "category": "data",
    },
    {
        "id": "analysis",
        "name": "Analysis Specialist",
        "description": "Computes scores (NEWS2, OEE) and identifies root causes from context",
        "category": "reasoning",
    },
    {
        "id": "action",
        "name": "Action Specialist",
        "description": "Generates recommendations, writes to external systems via MCP tools",
        "category": "action",
    },
]

GUARDRAIL_CATALOG = [
    {
        "id": "pii",
        "name": "PII Detection",
        "description": "Presidio + regex PII scanning (PDPA/GDPR)",
    },
    {
        "id": "toxicity",
        "name": "Toxicity Filter",
        "description": "Regex-based harmful content detection",
    },
    {
        "id": "hallucination",
        "name": "Hallucination Guard",
        "description": "Cross-check outputs against provided context",
    },
]

MODEL_TIERS = [
    {
        "id": "small",
        "name": "Small (Fast)",
        "description": "Quick responses, lower cost. Good for simple queries.",
    },
    {
        "id": "medium",
        "name": "Medium (Balanced)",
        "description": "Default tier. Balances speed and quality.",
    },
    {
        "id": "large",
        "name": "Large (Capable)",
        "description": "Best quality for complex reasoning tasks.",
    },
]


# ── Catalog endpoint ────────────────────────────────────────────────────────

@router.get("/catalog")
async def get_catalog() -> dict[str, Any]:
    """Return the available specialists, guardrails, and model tiers."""
    return {
        "specialists": SPECIALIST_CATALOG,
        "guardrails": GUARDRAIL_CATALOG,
        "model_tiers": MODEL_TIERS,
    }


# ── CRUD ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_configs(
    postgres: PostgresDep,
    domain: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List saved agent configurations."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if domain:
        conditions.append(f"domain = ${idx}")
        params.append(domain)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await postgres.fetch(
        f"SELECT * FROM agent_configs {where} ORDER BY is_default DESC, created_at DESC "
        f"LIMIT ${idx} OFFSET ${idx + 1}",
        *params, limit, offset,
    )
    total = await postgres.fetchval(
        f"SELECT COUNT(*) FROM agent_configs {where}", *params
    )
    return {"total": total or 0, "configs": [dict(r) for r in rows]}


@router.get("/{config_id}")
async def get_config(config_id: str, postgres: PostgresDep) -> dict[str, Any]:
    """Get a single agent configuration."""
    row = await postgres.fetch_one(
        "SELECT * FROM agent_configs WHERE id::text = $1 OR name = $1", config_id
    )
    if not row:
        raise HTTPException(404, f"Agent config '{config_id}' not found")
    return dict(row)


@router.post("", status_code=201)
async def create_config(body: AgentConfigCreate, postgres: PostgresDep) -> dict[str, Any]:
    """Create a new agent configuration."""
    import json

    config_id = str(uuid.uuid4())
    await postgres.execute(
        """INSERT INTO agent_configs
           (id, name, description, domain, model_tier, specialists,
            guardrails, budget_limit, max_iterations, is_default)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
        [
            config_id, body.name, body.description, body.domain,
            body.model_tier, json.dumps(body.specialists),
            json.dumps(body.guardrails), body.budget_limit,
            body.max_iterations, body.is_default,
        ],
    )
    return {"id": config_id, "name": body.name}


@router.put("/{config_id}")
async def update_config(
    config_id: str, body: AgentConfigUpdate, postgres: PostgresDep
) -> dict[str, Any]:
    """Update an agent configuration."""
    import json

    updates: list[str] = []
    params: list[Any] = []
    idx = 1

    for field_name, value in body.model_dump(exclude_none=True).items():
        if field_name in ("specialists", "guardrails"):
            updates.append(f"{field_name} = ${idx}")
            params.append(json.dumps(value))
        else:
            updates.append(f"{field_name} = ${idx}")
            params.append(value)
        idx += 1

    if not updates:
        raise HTTPException(400, "No fields to update")

    updates.append("updated_at = now()")
    params.append(config_id)
    await postgres.execute(
        f"UPDATE agent_configs SET {', '.join(updates)} WHERE id::text = ${idx} OR name = ${idx}",
        params,
    )
    return {"updated": True}


@router.delete("/{config_id}", status_code=204, response_class=Response)
async def delete_config(config_id: str, postgres: PostgresDep) -> Response:
    """Delete an agent configuration."""
    await postgres.execute(
        "DELETE FROM agent_configs WHERE id::text = $1 OR name = $1", [config_id]
    )
    return Response(status_code=204)
