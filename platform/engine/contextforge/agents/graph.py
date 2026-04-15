"""Production agent graph — LangGraph orchestration with PydanticAI agents.

Replaces the v3.0 single-node runtime.py with the full multi-agent
orchestration graph.  Each PydanticAI agent is wrapped in a LangGraph
node (see orchestrator.py, retrieval_agent.py, etc.).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
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
from contextforge.guardrails.layer import GuardrailsLayer

logger = logging.getLogger(__name__)


# ── Budget check node ─────────────────────────────────────────────────────────

async def budget_check(state: AgentState) -> dict[str, Any]:
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

async def context_check(state: AgentState) -> dict[str, Any]:
    """Compact context if it grows past the soft limit.

    The context window is approximated by summing the lengths of every value
    in ``state['context']`` plus the resolved-entity payload. When the total
    exceeds 24 000 characters (~6k tokens) we drop the oldest non-essential
    keys, keeping only ``query``, ``messages``, and ``resolved_entities``-
    derived facts. The trimmed map is returned via the state delta.
    """
    ctx = state.get("context") or {}
    if not isinstance(ctx, dict) or not ctx:
        return {}

    soft_limit = 24_000
    total = sum(len(str(v)) for v in ctx.values())
    if total <= soft_limit:
        return {}

    # Preserve a small allowlist of essential keys; drop the rest oldest-first.
    essential = {"query", "messages", "facts", "resolved_entities"}
    trimmed: dict[str, Any] = {k: v for k, v in ctx.items() if k in essential}
    logger.info(
        "context_check: compacted context %d → %d chars (dropped %d keys)",
        total,
        sum(len(str(v)) for v in trimmed.values()),
        len(ctx) - len(trimmed),
    )
    return {"context": trimmed}


# ── Guardrails check node ────────────────────────────────────────────────────

async def guardrails_check(state: AgentState) -> dict[str, Any]:
    """Validate agent output against the production guardrails layer."""
    # Pick the latest specialist output (action > analysis > retrieval).
    output_text = ""
    for key in ("action_result", "analysis_result", "retrieval_result"):
        result = state.get(key)
        if isinstance(result, dict):
            for field_name in ("output", "summary", "answer", "text"):
                value = result.get(field_name)
                if isinstance(value, str) and value:
                    output_text = value
                    break
            if output_text:
                break

    if not output_text:
        return {"guardrails_results": [{"status": "skipped", "reason": "no output yet"}]}

    layer = GuardrailsLayer(domain=state.get("domain", "industrial"))
    context_text = ""
    ctx = state.get("context")
    if isinstance(ctx, dict):
        context_text = " ".join(str(v) for v in ctx.values())[:8000]

    try:
        result = await layer.validate_output(
            {"output": output_text, "context": context_text}
        )
    except Exception as exc:  # noqa: BLE001 — never let guardrails crash the graph
        logger.exception("guardrails_check failed: %s", exc)
        return {"guardrails_results": [{"status": "error", "error": str(exc)}]}

    return {
        "guardrails_results": [
            {
                "status": "pass" if result["passed"] else "fail",
                "pii_found": result["pii_found"],
                "toxicity_found": result["toxicity_found"],
                "hallucination_found": result["hallucination_found"],
                "domain_issues": result["domain_issues"],
            }
        ]
    }


# ── Human review gate ─────────────────────────────────────────────────────────

async def human_review_gate(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop gate — graph pauses here via interrupt_before."""
    return {}


# ── Error recovery node ──────────────────────────────────────────────────────

async def error_recovery(state: AgentState) -> dict[str, Any]:
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

def build_production_graph() -> StateGraph[AgentState]:
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

async def create_agent(settings: Settings) -> tuple[CompiledStateGraph[AgentState], Any]:
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
    agent: CompiledStateGraph[AgentState],
    message: str,
    *,
    thread_id: str | None = None,
    domain: str = "industrial",
    user_id: str = "anonymous",
    budget_limit: float = 5.0,
) -> tuple[str, str, dict[str, float]]:
    """Send a user message through the production agent graph.

    Returns ``(response_text, thread_id, usage)`` where ``usage`` is
    ``{"tokens": int, "cost_usd": float}`` extracted from the final state
    so callers can record per-tenant usage.
    """
    thread_id = thread_id or str(uuid.uuid4())
    initial = _initial_state(message, thread_id, domain, user_id)
    initial["budget_limit"] = budget_limit
    result = await agent.ainvoke(  # type: ignore[call-overload]
        initial,
        config={"configurable": {"thread_id": thread_id}},
    )
    usage = {
        "tokens": float(result.get("total_tokens_used", 0) or 0),
        "cost_usd": float(result.get("total_cost_usd", 0.0) or 0.0),
    }
    return _format_response(result), thread_id, usage


def _initial_state(message: str, thread_id: str, domain: str, user_id: str) -> dict[str, Any]:
    return {
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
    }


def _format_response(result: dict[str, Any]) -> str:
    """Render a final agent state into the user-facing response string."""
    action = result.get("action_result")
    analysis = result.get("analysis_result")
    retrieval = result.get("retrieval_result")

    if action:
        return (
            f"{action.get('recommendation', '')}\n\n"
            f"Urgency: {action.get('urgency', 'unknown')}\n"
            f"Evidence: {action.get('evidence_summary', '')}"
        )
    if analysis:
        findings = "\n".join(f"- {f}" for f in analysis.get("findings", []))
        response = f"Findings:\n{findings}"
        if analysis.get("root_cause_hypothesis"):
            response += f"\n\nRoot cause: {analysis['root_cause_hypothesis']}"
        return response
    if retrieval:
        entities = retrieval.get("entities_found", [])
        response = f"Found {len(entities)} relevant entities."
        if retrieval.get("sources"):
            response += f"\nSources: {', '.join(retrieval['sources'])}"
        return response
    return "Analysis complete. No specific action required."


async def run_agent_chat_streaming(
    agent: CompiledStateGraph[AgentState],
    message: str,
    *,
    thread_id: str | None = None,
    domain: str = "industrial",
    user_id: str = "anonymous",
    budget_limit: float = 5.0,
) -> AsyncIterator[dict[str, Any]]:
    """Stream per-node state updates as the agent graph executes.

    Yields dicts with keys ``type`` (one of ``"node"``, ``"done"``, ``"error"``),
    ``thread_id``, and node-specific payload. The final ``done`` event carries
    the formatted ``response`` string and a ``usage`` dict so the caller can
    record per-tenant cost telemetry.
    """
    thread_id = thread_id or str(uuid.uuid4())
    state = _initial_state(message, thread_id, domain, user_id)
    state["budget_limit"] = budget_limit
    config: Any = {"configurable": {"thread_id": thread_id}}
    final_state: dict[str, Any] = {}

    try:
        async for event in agent.astream(state, config=config, stream_mode="updates"):  # type: ignore[call-overload]
            # `event` is {node_name: state_delta}
            for node_name, delta in event.items():
                if not isinstance(delta, dict):
                    continue
                final_state.update(delta)
                yield {
                    "type": "node",
                    "thread_id": thread_id,
                    "node": node_name,
                    "keys": sorted(delta.keys()),
                }
    except Exception as exc:
        logger.exception("run_agent_chat_streaming failed")
        yield {"type": "error", "thread_id": thread_id, "error": str(exc)}
        return

    yield {
        "type": "done",
        "thread_id": thread_id,
        "response": _format_response(final_state),
        "usage": {
            "tokens": int(final_state.get("total_tokens_used", 0) or 0),
            "cost_usd": float(final_state.get("total_cost_usd", 0.0) or 0.0),
        },
    }
