"""Tenant management + budget API."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep
from contextforge.tenancy.budget import TenantBudgetController
from contextforge.tenancy.context import get_current_tenant

router = APIRouter(prefix="/tenants")


# ── Models ──────────────────────────────────────────────────────────────────

class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    plan: str = Field("free", pattern=r"^(free|starter|pro|enterprise)$")


class BudgetUpdate(BaseModel):
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    max_requests: int | None = None


# ── Tenant CRUD ─────────────────────────────────────────────────────────────

@router.get("")
async def list_tenants(postgres: PostgresDep, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List all tenants."""
    rows = await postgres.fetch(
        "SELECT * FROM tenants ORDER BY created_at LIMIT $1 OFFSET $2",
        limit, offset,
    )
    total = await postgres.fetchval("SELECT COUNT(*) FROM tenants")
    return {"total": total or 0, "tenants": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_tenant(body: TenantCreate, postgres: PostgresDep) -> dict[str, Any]:
    """Create a new tenant with a default monthly budget."""

    tenant_id = str(uuid.uuid4())
    await postgres.execute(
        "INSERT INTO tenants (id, slug, name, plan) VALUES ($1, $2, $3, $4)",
        [tenant_id, body.slug, body.name, body.plan],
    )
    # Create default budget
    plan_defaults = {
        "free": (100_000, 5.0, 500),
        "starter": (1_000_000, 50.0, 5_000),
        "pro": (5_000_000, 200.0, 25_000),
        "enterprise": (10_000_000, 500.0, 100_000),
    }
    tokens, cost, reqs = plan_defaults.get(body.plan, plan_defaults["free"])
    await postgres.execute(
        """INSERT INTO tenant_budgets (tenant_id, period, max_tokens, max_cost_usd, max_requests)
           VALUES ($1::uuid, 'monthly', $2, $3, $4)""",
        [tenant_id, tokens, cost, reqs],
    )
    return {"id": tenant_id, "slug": body.slug}


@router.get("/current")
async def current_tenant() -> dict[str, Any]:
    """Return the tenant for the current request context."""
    ctx = get_current_tenant()
    return {
        "tenant_id": ctx.tenant_id,
        "slug": ctx.slug,
        "name": ctx.name,
        "plan": ctx.plan,
        "kg_namespace": ctx.kg_namespace,
        "qdrant_prefix": ctx.qdrant_prefix,
    }


# ── Budget endpoints ────────────────────────────────────────────────────────

@router.get("/{tenant_ref}/budget")
async def get_budget(tenant_ref: str, postgres: PostgresDep) -> dict[str, Any]:
    """Get budget status for a tenant."""
    # Resolve tenant_id from slug or id
    row = await postgres.fetch_one(
        "SELECT id FROM tenants WHERE id::text = $1 OR slug = $1", tenant_ref
    )
    if not row:
        raise HTTPException(404, f"Tenant '{tenant_ref}' not found")

    controller = TenantBudgetController(postgres)
    status = await controller.get_budget(str(row["id"]))
    if status is None:
        raise HTTPException(404, "No budget configured for this tenant")
    return status.to_dict()


@router.put("/{tenant_ref}/budget")
async def update_budget(
    tenant_ref: str, body: BudgetUpdate, postgres: PostgresDep
) -> dict[str, Any]:
    """Update budget limits for a tenant."""
    row = await postgres.fetch_one(
        "SELECT id FROM tenants WHERE id::text = $1 OR slug = $1", tenant_ref
    )
    if not row:
        raise HTTPException(404, f"Tenant '{tenant_ref}' not found")

    controller = TenantBudgetController(postgres)
    await controller.update_limits(
        str(row["id"]),
        max_tokens=body.max_tokens,
        max_cost_usd=body.max_cost_usd,
        max_requests=body.max_requests,
    )
    return {"updated": True}


@router.get("/{tenant_ref}/usage")
async def get_usage(
    tenant_ref: str, postgres: PostgresDep, limit: int = 50
) -> dict[str, Any]:
    """Get recent usage log for a tenant."""
    row = await postgres.fetch_one(
        "SELECT id FROM tenants WHERE id::text = $1 OR slug = $1", tenant_ref
    )
    if not row:
        raise HTTPException(404, f"Tenant '{tenant_ref}' not found")

    tenant_id = str(row["id"])
    rows = await postgres.fetch(
        """SELECT operation, tokens_used, cost_usd, user_id, created_at
           FROM tenant_usage_log
           WHERE tenant_id = $1::uuid
           ORDER BY created_at DESC
           LIMIT $2""",
        tenant_id, limit,
    )
    return {"tenant_id": tenant_id, "usage": [dict(r) for r in rows]}
