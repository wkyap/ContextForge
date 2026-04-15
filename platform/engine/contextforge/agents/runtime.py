"""Minimal LangGraph agent runtime with LiteLLM and PostgreSQL checkpointing.

This is the Session-6 vertical slice: a single-node chat agent that
proves the full stack (LiteLLM → LLM → LangGraph → Postgres checkpoint →
Langfuse trace) works end-to-end.  It will be expanded in Phase 4 into
the multi-agent orchestrator.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any, TypedDict

import litellm
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from contextforge.config import Settings

logger = logging.getLogger(__name__)


# ── State schema ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Sequence[BaseMessage]


# ── Graph builder ─────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph[AgentState]:
    """Construct a single-node LangGraph that calls LiteLLM."""

    async def chat_node(state: AgentState) -> dict[str, Any]:
        """Call the LLM via LiteLLM and append the response."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "You are ContextForge, an AI assistant."},
        ]
        for msg in state["messages"]:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})

        response = await litellm.acompletion(
            model="openai/gpt-4o-mini",
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        return {"messages": [AIMessage(content=content)]}

    graph = StateGraph(AgentState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)
    return graph


# ── Compiled graph factory ────────────────────────────────────────────────────

async def create_agent(settings: Settings) -> tuple[CompiledStateGraph[AgentState], Any]:
    """Return a compiled LangGraph agent with async Postgres checkpointing.

    Returns (compiled_graph, checkpointer_context) — caller must keep the
    context alive for the lifetime of the application.
    """
    checkpointer_ctx = AsyncPostgresSaver.from_conn_string(settings.postgres_dsn)
    checkpointer = await checkpointer_ctx.__aenter__()
    await checkpointer.setup()

    graph = _build_graph()
    return graph.compile(checkpointer=checkpointer), checkpointer_ctx


# ── Convenience runner ────────────────────────────────────────────────────────

async def run_agent_chat(
    agent: CompiledStateGraph[AgentState],
    message: str,
    *,
    thread_id: str | None = None,
) -> tuple[str, str]:
    """Send a user message and return (response_text, thread_id).

    If *thread_id* is ``None`` a new conversation thread is created.
    """
    thread_id = thread_id or str(uuid.uuid4())

    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": thread_id}},
    )

    last_msg = result["messages"][-1]
    return last_msg.content, thread_id
