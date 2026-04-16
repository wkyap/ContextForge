"""Retrieval specialist — PydanticAI agent + LangGraph node wrapper.

Gathers context from the knowledge graph, time series database, and vector
store.  Output is a validated ``RetrievalResult`` with provenance trail.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent

from contextforge.agents.deps import AgentDeps
from contextforge.agents.schemas import RetrievalResult
from contextforge.agents.state import AgentState

logger = logging.getLogger(__name__)

# ── PydanticAI Agent ──────────────────────────────────────────────────────────

retrieval_specialist = Agent(
    model="litellm:anthropic/claude-sonnet-4-6",
    deps_type=AgentDeps,
    output_type=RetrievalResult,
    instructions=(
        "You are the retrieval specialist for ContextForge.\n"
        "Use the MCP tools to gather context from the knowledge graph, "
        "time series database, and vector store.\n"
        "Always include provenance in your sources list.\n"
        "Try the cheapest retrieval path first — only escalate if confidence "
        "is below 0.7."
    ),
    retries=2,
)


# ── Cost helper ───────────────────────────────────────────────────────────────

def _estimate_cost(usage: Any) -> float:
    total = getattr(usage, "total_tokens", 0) if usage else 0
    return total * 0.000003


# ── LangGraph node wrapper ────────────────────────────────────────────────────

async def retrieval_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node wrapping the PydanticAI retrieval specialist."""
    deps = AgentDeps(
        domain=state.get("domain", "industrial"),
        db_uri="",
        skill_catalog=state.get("context", {}).get("skill_catalog", {}),
        budget_remaining_usd=(
            state.get("budget_limit", 1.0) - state.get("total_cost_usd", 0)
        ),
        user_id=state.get("user_id", "anonymous"),
    )

    prompt = (
        f"Query: {state['query']}\n"
        f"Plan: {state.get('orchestrator_plan', {})}"
    )
    result = await retrieval_specialist.run(prompt, deps=deps)

    return {
        "retrieval_result": result.output.model_dump(),
        "context": {
            **state.get("context", {}),
            "retrieval": result.output.model_dump(),
        },
        "total_tokens_used": (
            state.get("total_tokens_used", 0)
            + getattr(result.usage(), "total_tokens", 0)
        ),
        "total_cost_usd": (
            state.get("total_cost_usd", 0) + _estimate_cost(result.usage())
        ),
        "tools_called": state.get("tools_called", []) + ["retrieval"],
    }
