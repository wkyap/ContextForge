"""Action specialist — PydanticAI agent + LangGraph node wrapper.

Recommends actions based on analysis results, matches SOPs, and assesses
urgency.  Output is a validated ``ActionResult``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent

from contextforge.agents.deps import AgentDeps
from contextforge.agents.schemas import ActionResult
from contextforge.agents.state import AgentState

logger = logging.getLogger(__name__)

# ── PydanticAI Agent ──────────────────────────────────────────────────────────

action_specialist = Agent(
    model="litellm:anthropic/claude-sonnet-4-6",
    deps_type=AgentDeps,
    output_type=ActionResult,
    instructions=(
        "You are the action specialist for ContextForge.\n"
        "Based on analysis results, recommend specific actions, match SOPs, "
        "and assess urgency.\n"
        "Flag anything requiring human approval by setting "
        "requires_human_approval=true."
    ),
    retries=2,
)


# ── Cost helper ───────────────────────────────────────────────────────────────

def _estimate_cost(usage: Any) -> float:
    total = getattr(usage, "total_tokens", 0) if usage else 0
    return total * 0.000003


# ── LangGraph node wrapper ────────────────────────────────────────────────────

async def action_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node wrapping the PydanticAI action specialist."""
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
        f"Analysis: {state.get('analysis_result', {})}\n"
        f"Context: {state.get('retrieval_result', {})}"
    )
    result = await action_specialist.run(prompt, deps=deps)

    return {
        "action_result": result.output.model_dump(),
        "total_tokens_used": (
            state.get("total_tokens_used", 0)
            + getattr(result.usage(), "total_tokens", 0)
        ),
        "total_cost_usd": (
            state.get("total_cost_usd", 0) + _estimate_cost(result.usage())
        ),
        "tools_called": state.get("tools_called", []) + ["action"],
    }
