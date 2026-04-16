"""Agent state — shared TypedDict flowing through the LangGraph state graph."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes.

    PydanticAI agents read from and write to this state via their
    LangGraph node wrappers (see orchestrator.py, retrieval_agent.py, etc.).
    """

    messages: Annotated[list[Any], operator.add]
    query: str
    domain: str
    user_id: str
    thread_id: str
    resolved_entities: list[dict[str, Any]]
    context: dict[str, Any]
    loaded_skills: list[str]

    # Budget tracking
    budget_limit: float
    total_tokens_used: int
    total_cost_usd: float
    iteration_count: int
    tools_called: list[str]

    # Error tracking
    errors: list[dict[str, Any]]
    retry_count: int
    fallback_triggered: bool

    # Guardrails
    guardrails_results: list[dict[str, Any]]

    # PydanticAI structured outputs (carried in state for downstream nodes)
    orchestrator_plan: dict[str, Any] | None
    retrieval_result: dict[str, Any] | None
    analysis_result: dict[str, Any] | None
    action_result: dict[str, Any] | None
