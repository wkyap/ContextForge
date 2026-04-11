"""Agents API — PydanticAI + LangGraph hybrid chat (v3.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from contextforge.agents.graph import run_agent_chat
from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/agent")


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    thread_id: str | None = None
    domain: str = "industrial"


class ChatResponse(BaseModel):
    response: str
    thread_id: str


# ── POST /agent/chat ─────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(body: ChatRequest, request: Request) -> ChatResponse:
    agent = request.app.state.agent
    response_text, thread_id = await run_agent_chat(
        agent,
        body.message,
        thread_id=body.thread_id,
        domain=body.domain,
    )
    return ChatResponse(response=response_text, thread_id=thread_id)


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
    template_id: str, body: TemplateRunRequest, request: Request
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
    response_text, thread_id = await run_agent_chat(
        agent,
        rendered,
        thread_id=body.thread_id,
        domain=body.domain,
    )
    return ChatResponse(response=response_text, thread_id=thread_id)


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
