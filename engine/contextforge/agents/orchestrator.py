"""Orchestrator agent — PydanticAI agent + LangGraph node wrapper.

The orchestrator analyses the user query, selects specialists, and decides
which SKILL.md files to load.  Its output is a validated ``OrchestratorPlan``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent, RunContext

from contextforge.agents.deps import AgentDeps
from contextforge.agents.schemas import OrchestratorPlan
from contextforge.agents.state import AgentState

logger = logging.getLogger(__name__)

# ── PydanticAI Agent ──────────────────────────────────────────────────────────

orchestrator = Agent(
    model="litellm:anthropic/claude-sonnet-4-6",
    deps_type=AgentDeps,
    output_type=OrchestratorPlan,
    instructions=(
        "You are the orchestrator for the ContextForge platform.\n"
        "Given a user query, determine which specialists to invoke and which "
        "SKILL.md files to load. Available specialists: retrieval, analysis, action.\n"
        "Consult the skill catalog in your dependencies to find relevant skills."
    ),
    retries=2,
)


@orchestrator.tool
async def search_skill_catalog(ctx: RunContext[AgentDeps], query: str) -> list[dict]:
    """Search the SKILL.md catalog for relevant skills."""
    catalog = ctx.deps.skill_catalog
    if isinstance(catalog, dict):
        return [
            {"name": name, "description": meta}
            for name, meta in catalog.items()
            if query.lower() in name.lower()
            or query.lower() in str(meta).lower()
        ]
    return []


# ── Cost helper ───────────────────────────────────────────────────────────────

def _estimate_cost(usage: Any) -> float:
    """Rough cost estimate from PydanticAI usage stats."""
    total = getattr(usage, "total_tokens", 0) if usage else 0
    return total * 0.000003  # ~$3/M tokens (Sonnet-tier default)


# ── LangGraph node wrapper ────────────────────────────────────────────────────

async def orchestrator_node(state: AgentState) -> dict:
    """LangGraph node that wraps the PydanticAI orchestrator agent."""
    deps = AgentDeps(
        domain=state.get("domain", "industrial"),
        db_uri="",
        skill_catalog=state.get("context", {}).get("skill_catalog", {}),
        budget_remaining_usd=(
            state.get("budget_limit", 1.0) - state.get("total_cost_usd", 0)
        ),
        user_id=state.get("user_id", "anonymous"),
    )

    result = await orchestrator.run(state["query"], deps=deps)

    return {
        "orchestrator_plan": result.output.model_dump(),
        "loaded_skills": result.output.skills_to_load,
        "total_tokens_used": (
            state.get("total_tokens_used", 0)
            + getattr(result.usage(), "total_tokens", 0)
        ),
        "total_cost_usd": (
            state.get("total_cost_usd", 0) + _estimate_cost(result.usage())
        ),
        "iteration_count": state.get("iteration_count", 0) + 1,
    }
