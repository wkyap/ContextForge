"""Agents API — PydanticAI + LangGraph hybrid chat (v3.1)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from contextforge.agents.graph import run_agent_chat

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
async def list_agent_templates(request: Request) -> list[dict]:
    """List SKILL.md files of type 'template'."""
    registry = request.app.state.skill_registry
    templates = [
        {"name": s.name, "description": s.description, "domain": s.domain}
        for s in registry.list_by_type("template")
    ]
    return templates


@router.post("/templates/{template_id}/run")
async def run_agent_template(template_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": "Template execution not yet implemented"},
    )


# ── Sessions ─────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"detail": "Session listing not yet implemented"},
    )
