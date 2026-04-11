"""Analysis specialist — PydanticAI agent + LangGraph node wrapper.

Correlates data from retrieval results to identify patterns, compute scores,
and form root cause hypotheses.  Output is a validated ``AnalysisResult``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent

from contextforge.agents.deps import AgentDeps
from contextforge.agents.schemas import AnalysisResult
from contextforge.agents.state import AgentState

logger = logging.getLogger(__name__)

# ── PydanticAI Agent ──────────────────────────────────────────────────────────

analysis_specialist = Agent(
    model="litellm:anthropic/claude-opus-4-6",
    deps_type=AgentDeps,
    output_type=AnalysisResult,
    instructions=(
        "You are the analysis specialist for ContextForge.\n"
        "Correlate data from retrieval results to identify patterns, "
        "compute scores, and form root cause hypotheses.\n"
        "NEVER infer clinical/engineering scores — use the compute MCP "
        "tool for deterministic calculations.\n"
        "Keep output structured and concise."
    ),
    retries=2,
)


# ── Cost helper ───────────────────────────────────────────────────────────────

def _estimate_cost(usage: Any) -> float:
    total = getattr(usage, "total_tokens", 0) if usage else 0
    return total * 0.000015  # Opus-tier pricing


# ── LangGraph node wrapper ────────────────────────────────────────────────────

async def analysis_node(state: AgentState) -> dict[str, Any]:
    """LangGraph node wrapping the PydanticAI analysis specialist."""
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
        f"Retrieved context: {state.get('retrieval_result', {})}"
    )
    result = await analysis_specialist.run(prompt, deps=deps)

    return {
        "analysis_result": result.output.model_dump(),
        "context": {
            **state.get("context", {}),
            "analysis": result.output.model_dump(),
        },
        "total_tokens_used": (
            state.get("total_tokens_used", 0)
            + getattr(result.usage(), "total_tokens", 0)
        ),
        "total_cost_usd": (
            state.get("total_cost_usd", 0) + _estimate_cost(result.usage())
        ),
        "tools_called": state.get("tools_called", []) + ["analysis"],
    }
