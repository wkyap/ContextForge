"""Onboarding API — AI-guided domain onboarding wizard."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep
from contextforge.onboarding.domain_wizard import DomainOnboardingWizard

router = APIRouter(prefix="/onboarding")


# ── Models ───────────────────────────────────────────────────────────────────

class DomainOnboardRequest(BaseModel):
    domain_name: str = Field(..., max_length=100, pattern="^[a-z][a-z0-9_-]*$")
    description: str = Field(..., min_length=10, max_length=2000)
    example_entities: list[str] = []


class DomainPlanApproval(BaseModel):
    approved: bool
    modifications: dict[str, Any] | None = None


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/domain")
async def onboard_domain(body: DomainOnboardRequest, postgres: PostgresDep) -> dict[str, Any]:
    """Generate an AI domain onboarding plan with SKILL.md files."""
    wizard = DomainOnboardingWizard()
    plan = await wizard.generate_domain_plan(
        domain_name=body.domain_name,
        description=body.description,
        example_entities=body.example_entities,
    )
    validation = await wizard.validate_plan(plan)

    # Persist the plan for later review
    plan_id = str(uuid.uuid4())
    await postgres.execute(
        """
        INSERT INTO onboarding_plans (id, domain_name, description, plan, validation, status)
        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, 'draft')
        """,
        plan_id, body.domain_name, body.description,
        json.dumps(plan), json.dumps(validation),
    )

    return {
        "plan_id": plan_id,
        "domain_name": body.domain_name,
        "plan": plan,
        "validation": validation,
    }


@router.get("/plans")
async def list_plans(postgres: PostgresDep) -> dict[str, Any]:
    rows = await postgres.fetch(
        """
        SELECT id, domain_name, description, status, created_at
        FROM onboarding_plans
        ORDER BY created_at DESC
        LIMIT 50
        """
    )
    return {"count": len(rows), "plans": [dict(r) for r in rows]}


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str, postgres: PostgresDep) -> dict[str, Any]:
    row = await postgres.fetchrow(
        "SELECT * FROM onboarding_plans WHERE id = $1", plan_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return dict(row)


@router.post("/plans/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    body: DomainPlanApproval,
    postgres: PostgresDep,
) -> dict[str, Any]:
    row = await postgres.fetchrow(
        "SELECT * FROM onboarding_plans WHERE id = $1", plan_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    if row["status"] != "draft":
        raise HTTPException(status_code=400, detail=f"Plan is already {row['status']}")

    if body.approved:
        plan = row["plan"]
        if body.modifications:
            plan.update(body.modifications)

        domain_name = row["domain_name"]
        domain_dir = Path(__file__).resolve().parents[3] / "domains" / domain_name

        # Create domain directory structure
        for subdir in ("schema", "ingestion", "tools", "templates", "guardrails", "channels"):
            (domain_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Write generated SKILL.md files
        written_files: list[str] = []
        for et in plan.get("entity_types", []):
            if et.get("skill_md"):
                path = domain_dir / "schema" / f"{et['name']}.md"
                path.write_text(et["skill_md"], encoding="utf-8")
                written_files.append(str(path.relative_to(domain_dir)))

        for ing in plan.get("ingestion_skills", []):
            if ing.get("skill_md"):
                path = domain_dir / "ingestion" / f"{ing['name']}.md"
                path.write_text(ing["skill_md"], encoding="utf-8")
                written_files.append(str(path.relative_to(domain_dir)))

        await postgres.execute(
            "UPDATE onboarding_plans SET status = 'approved', plan = $2::jsonb WHERE id = $1",
            plan_id, json.dumps(plan),
        )

        return {
            "plan_id": plan_id,
            "status": "approved",
            "domain_dir": str(domain_dir),
            "files_written": written_files,
        }
    else:
        await postgres.execute(
            "UPDATE onboarding_plans SET status = 'rejected' WHERE id = $1",
            plan_id,
        )
        return {"plan_id": plan_id, "status": "rejected"}
