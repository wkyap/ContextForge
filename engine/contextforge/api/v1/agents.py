"""Agents API — PydanticAI + LangGraph hybrid chat (v3.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from contextforge.agents.graph import run_agent_chat
from contextforge.api.deps import PostgresDep, TenantDep
from contextforge.tenancy.budget import TenantBudgetController

router = APIRouter(prefix="/agent")


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    thread_id: str | None = None
    domain: str = "industrial"


class ChatUsage(BaseModel):
    tokens: int
    cost_usd: float


class ChatResponse(BaseModel):
    response: str
    thread_id: str
    usage: ChatUsage | None = None


async def _enforce_and_record(
    postgres: Any,
    tenant_id: str,
    user_id: str,
    operation: str,
    runner: Any,
) -> tuple[str, str, dict[str, float]]:
    """Block if tenant is over budget, run the agent, persist usage."""
    controller = TenantBudgetController(postgres)
    if not await controller.check_budget(tenant_id):
        raise HTTPException(
            status_code=429,
            detail="Tenant budget exceeded for the current period",
        )
    response_text, thread_id, usage = await runner()
    try:
        await controller.record_usage(
            tenant_id,
            tokens=int(usage.get("tokens", 0)),
            cost_usd=float(usage.get("cost_usd", 0.0)),
            user_id=user_id,
            operation=operation,
        )
    except Exception:  # pragma: no cover — usage tracking must never block the response
        pass
    return response_text, thread_id, usage


# ── POST /agent/chat ─────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    body: ChatRequest, request: Request, postgres: PostgresDep, tenant: TenantDep
) -> ChatResponse:
    agent = request.app.state.agent

    async def _run() -> tuple[str, str, dict[str, float]]:
        return await run_agent_chat(
            agent,
            body.message,
            thread_id=body.thread_id,
            domain=body.domain,
            user_id=tenant.tenant_id,
        )

    response_text, thread_id, usage = await _enforce_and_record(
        postgres, tenant.tenant_id, tenant.tenant_id, "agent_chat", _run,
    )
    return ChatResponse(
        response=response_text,
        thread_id=thread_id,
        usage=ChatUsage(tokens=int(usage["tokens"]), cost_usd=usage["cost_usd"]),
    )


# ── Agent templates ──────────────────────────────────────────────────────────

@router.get("/templates")
async def list_agent_templates(request: Request) -> list[dict[str, Any]]:
    """List SKILL.md files of type 'template'."""
    registry = request.app.state.skill_registry
    templates = [
        {"name": s.name, "description": s.description, "domain": s.domain}
        for s in registry.list_by_type("template")
    ]
    return templates


class TemplateRunRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    thread_id: str | None = None
    domain: str = "industrial"


@router.post("/templates/{template_id}/run", response_model=ChatResponse)
async def run_agent_template(
    template_id: str,
    body: TemplateRunRequest,
    request: Request,
    postgres: PostgresDep,
    tenant: TenantDep,
) -> ChatResponse:
    """Render a template SKILL.md body with variables and run it through the agent."""
    registry = request.app.state.skill_registry
    skill = registry.get(template_id)
    if skill is None or skill.type != "template":
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")

    rendered = skill.body
    for key, value in body.variables.items():
        placeholder = "{{" + key + "}}"
        rendered = rendered.replace(placeholder, str(value))

    agent = request.app.state.agent

    async def _run() -> tuple[str, str, dict[str, float]]:
        return await run_agent_chat(
            agent,
            rendered,
            thread_id=body.thread_id,
            domain=body.domain,
            user_id=tenant.tenant_id,
        )

    response_text, thread_id, usage = await _enforce_and_record(
        postgres, tenant.tenant_id, tenant.tenant_id, f"template:{template_id}", _run,
    )
    return ChatResponse(
        response=response_text,
        thread_id=thread_id,
        usage=ChatUsage(tokens=int(usage["tokens"]), cost_usd=usage["cost_usd"]),
    )


# ── Sessions ─────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    postgres: PostgresDep, limit: int = 50, offset: int = 0
) -> dict[str, Any]:
    """List recent agent chat sessions (distinct thread_ids from LangGraph checkpoints)."""
    rows = await postgres.fetch(
        """
        SELECT thread_id,
               COUNT(*) AS checkpoint_count,
               MAX(checkpoint_id) AS latest_checkpoint_id
        FROM checkpoints
        WHERE checkpoint_ns = ''
        GROUP BY thread_id
        ORDER BY MAX(checkpoint_id) DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    total = await postgres.fetchval(
        "SELECT COUNT(DISTINCT thread_id) FROM checkpoints WHERE checkpoint_ns = ''"
    )
    return {
        "total": total or 0,
        "limit": limit,
        "offset": offset,
        "sessions": [
            {
                "thread_id": r["thread_id"],
                "checkpoint_count": r["checkpoint_count"],
                "latest_checkpoint_id": r["latest_checkpoint_id"],
            }
            for r in rows
        ],
    }
