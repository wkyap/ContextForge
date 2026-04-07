"""Production agent graph — LangGraph orchestration with PydanticAI agents.

Replaces the v3.0 single-node runtime.py with the full multi-agent
orchestration graph.  Each PydanticAI agent is wrapped in a LangGraph
node (see orchestrator.py, retrieval_agent.py, etc.).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from contextforge.agents.action_agent import action_node
from contextforge.agents.analysis_agent import analysis_node
from contextforge.agents.orchestrator import orchestrator_node
from contextforge.agents.retrieval_agent import retrieval_node
from contextforge.agents.state import AgentState
from contextforge.config import Settings

logger = logging.getLogger(__name__)


# ── Budget check node ─────────────────────────────────────────────────────────

async def budget_check(state: AgentState) -> dict:
    """Check if we've exceeded budget limits."""
    max_tokens = 100_000
    max_cost = state.get("budget_limit", 5.0)
    max_iterations = 15

    if (
        state.get("total_tokens_used", 0) >= max_tokens
        or state.get("total_cost_usd", 0) >= max_cost
        or state.get("iteration_count", 0) >= max_iterations
    ):
        return {"errors": [{"type": "budget_exceeded", "message": "Budget limit reached"}]}
    return {}


# ── Context check node ────────────────────────────────────────────────────────

async def context_check(state: AgentState) -> dict:
    """Check context window budget and trigger compaction if needed."""
    # Placeholder — full implementation in context/cache_manager.py
    return {}


# ── Guardrails check node ────────────────────────────────────────────────────

async def guardrails_check(state: AgentState) -> dict:
    """Validate agent output against guardrails."""
    # Placeholder — wired to guardrails/layer.py at runtime
    return {"guardrails_results": [{"status": "pass"}]}


# ── Human review gate ─────────────────────────────────────────────────────────

async def human_review_gate(state: AgentState) -> dict:
    """Human-in-the-loop gate — graph pauses here via interrupt_before."""
    return {}


# ── Error recovery node ──────────────────────────────────────────────────────

async def error_recovery(state: AgentState) -> dict:
    """Handle errors and decide: retry, fallback, or escalate."""
    retry_count = state.get("retry_count", 0)

    if retry_count >= 3:
        return {"fallback_triggered": True}

    return {"retry_count": retry_count + 1, "errors": []}


# ── Routing functions ─────────────────────────────────────────────────────────

def route_to_specialist(state: AgentState) -> str:
    """Route from orchestrator to the appropriate specialist."""
    plan = state.get("orchestrator_plan", {})
    if not plan:
        return "conclude"

    # Check budget
    if state.get("total_cost_usd", 0) >= state.get("budget_limit", 5.0):
        return "budget_exceeded"

    specialists = plan.get("specialists_needed", [])

    # Route to the first specialist not yet called
    called = set(state.get("tools_called", []))
    for spec in specialists:
        if spec == "retrieval" and "retrieval" not in called:
            return "retrieve"
        if spec == "analysis" and "analysis" not in called:
            return "analyze"
        if spec == "action" and "action" not in called:
            return "act"

    return "conclude"


def route_after_specialist(state: AgentState) -> str:
    """After a specialist completes, route to error recovery or back to budget check."""
    if state.get("errors"):
        return "error_recovery"
    return "budget_check"


def route_error_recovery(state: AgentState) -> str:
    """Decide how to handle an error: retry, fallback, or escalate."""
    if state.get("fallback_triggered"):
        return "fallback"
    if state.get("retry_count", 0) >= 3:
        return "human_escalation"
    return "retry"


def route_guardrails(state: AgentState) -> str:
    """Route based on guardrails outcome."""
    results = state.get("guardrails_results", [])
    if not results:
        return "pass"

    last = results[-1] if results else {}
    status = last.get("status", "pass")

    if status == "block":
        return "block"
    if status == "rewrite":
        return "rewrite"
    return "pass"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_production_graph() -> StateGraph:
    """Construct the full multi-agent orchestration graph.

    Structure:
      budget_check → context_check → orchestrator → specialist(s) → guardrails → END
      with error recovery and human-in-the-loop gates.
    """
    graph = StateGraph(AgentState)

    # Nodes — each wraps a PydanticAI agent
    graph.add_node("budget_check", budget_check)
    graph.add_node("context_check", context_check)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("retrieval_specialist", retrieval_node)
    graph.add_node("analysis_specialist", analysis_node)
    graph.add_node("action_specialist", action_node)
    graph.add_node("guardrails_check", guardrails_check)
    graph.add_node("error_recovery", error_recovery)
    graph.add_node("human_review", human_review_gate)

    # Flow
    graph.set_entry_point("budget_check")
    graph.add_edge("budget_check", "context_check")
    graph.add_edge("context_check", "orchestrator")

    # Orchestrator routes to specialists based on OrchestratorPlan
    graph.add_conditional_edges(
        "orchestrator",
        route_to_specialist,
        {
            "retrieve": "retrieval_specialist",
            "analyze": "analysis_specialist",
            "act": "action_specialist",
            "conclude": "guardrails_check",
            "budget_exceeded": "guardrails_check",
        },
    )

    # Specialists return to budget check for next iteration
    for specialist in [
        "retrieval_specialist",
        "analysis_specialist",
        "action_specialist",
    ]:
        graph.add_conditional_edges(
            specialist,
            route_after_specialist,
            {"budget_check": "budget_check", "error_recovery": "error_recovery"},
        )

    # Error recovery routes
    graph.add_conditional_edges(
        "error_recovery",
        route_error_recovery,
        {
            "retry": "budget_check",
            "fallback": "guardrails_check",
            "human_escalation": "human_review",
        },
    )

    # Guardrails gate
    graph.add_conditional_edges(
        "guardrails_check",
        route_guardrails,
        {"pass": END, "block": "human_review", "rewrite": "orchestrator"},
    )

    graph.add_edge("human_review", END)

    return graph


# ── Compiled graph factory ────────────────────────────────────────────────────

async def create_agent(settings: Settings) -> tuple[CompiledStateGraph, Any]:
    """Return a compiled production agent graph with Postgres checkpointing.

    Returns ``(compiled_graph, checkpointer_context)`` — caller must keep
    the context alive for the application lifetime.
    """
    checkpointer_ctx = AsyncPostgresSaver.from_conn_string(settings.postgres_dsn)
    checkpointer = await checkpointer_ctx.__aenter__()
    await checkpointer.setup()

    graph = build_production_graph()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_review"],
    )

    return compiled, checkpointer_ctx


# ── Convenience runner ────────────────────────────────────────────────────────

async def run_agent_chat(
    agent: CompiledStateGraph,
    message: str,
    *,
    thread_id: str | None = None,
    domain: str = "industrial",
    user_id: str = "anonymous",
) -> tuple[str, str]:
    """Send a user message through the production agent graph.

    Returns ``(response_text, thread_id)``.
    """
    thread_id = thread_id or str(uuid.uuid4())

    result = await agent.ainvoke(
        {
            "messages": [{"role": "user", "content": message}],
            "query": message,
            "domain": domain,
            "user_id": user_id,
            "thread_id": thread_id,
            "resolved_entities": [],
            "context": {},
            "loaded_skills": [],
            "budget_limit": 5.0,
            "total_tokens_used": 0,
            "total_cost_usd": 0.0,
            "iteration_count": 0,
            "tools_called": [],
            "errors": [],
            "retry_count": 0,
            "fallback_triggered": False,
            "guardrails_results": [],
            "orchestrator_plan": None,
            "retrieval_result": None,
            "analysis_result": None,
            "action_result": None,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    # Extract response from the structured outputs
    action = result.get("action_result")
    analysis = result.get("analysis_result")
    retrieval = result.get("retrieval_result")

    if action:
        response = (
            f"{action.get('recommendation', '')}\n\n"
            f"Urgency: {action.get('urgency', 'unknown')}\n"
            f"Evidence: {action.get('evidence_summary', '')}"
        )
    elif analysis:
        findings = "\n".join(f"- {f}" for f in analysis.get("findings", []))
        response = f"Findings:\n{findings}"
        if analysis.get("root_cause_hypothesis"):
            response += f"\n\nRoot cause: {analysis['root_cause_hypothesis']}"
    elif retrieval:
        entities = retrieval.get("entities_found", [])
        response = f"Found {len(entities)} relevant entities."
        if retrieval.get("sources"):
            response += f"\nSources: {', '.join(retrieval['sources'])}"
    else:
        response = "Analysis complete. No specific action required."

    return response, thread_id
