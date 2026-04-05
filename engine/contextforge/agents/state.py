"""Agent state — shared TypedDict flowing through the LangGraph state graph."""

from __future__ import annotations

from typing import Annotated, TypedDict

import operator


class AgentState(TypedDict):
    """Shared state across all LangGraph nodes.

    PydanticAI agents read from and write to this state via their
    LangGraph node wrappers (see orchestrator.py, retrieval_agent.py, etc.).
    """

    messages: Annotated[list, operator.add]
    query: str
    domain: str
    user_id: str
    thread_id: str
    resolved_entities: list[dict]
    context: dict
    loaded_skills: list[str]

    # Budget tracking
    budget_limit: float
    total_tokens_used: int
    total_cost_usd: float
    iteration_count: int
    tools_called: list[str]

    # Error tracking
    errors: list[dict]
    retry_count: int
    fallback_triggered: bool

    # Guardrails
    guardrails_results: list[dict]

    # PydanticAI structured outputs (carried in state for downstream nodes)
    orchestrator_plan: dict | None
    retrieval_result: dict | None
    analysis_result: dict | None
    action_result: dict | None
