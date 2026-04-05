"""Decorators for structured tracing via Langfuse.

Usage::

    @trace_agent("orchestrator")
    async def run_orchestrator(state): ...

    @trace_span("retrieval")
    async def retrieve_context(query): ...

    @trace_tool("neo4j_query")
    async def run_cypher(query, params): ...
"""

from __future__ import annotations

import functools
import time
import uuid
from typing import Any, Callable

from contextforge.observability.langfuse_setup import get_langfuse


def _make_trace_id() -> str:
    return str(uuid.uuid4())


# ── Agent-level trace (top-level run) ─────────────────────────────────────────

def trace_agent(name: str) -> Callable:
    """Create a top-level Langfuse trace for an agent invocation."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse = get_langfuse()
            trace = langfuse.trace(
                id=_make_trace_id(),
                name=name,
                metadata={"function": fn.__qualname__},
            )
            kwargs["_trace"] = trace
            try:
                result = await fn(*args, **kwargs)
                trace.update(output={"status": "success"})
                return result
            except Exception as exc:
                trace.update(
                    output={"status": "error", "error": str(exc)},
                    level="ERROR",
                )
                raise

        return wrapper

    return decorator


# ── Span (sub-step within a trace) ────────────────────────────────────────────

def trace_span(name: str) -> Callable:
    """Create a Langfuse span for a sub-step.  Expects ``_trace`` in kwargs."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            trace = kwargs.get("_trace")
            if trace is None:
                return await fn(*args, **kwargs)

            span = trace.span(name=name)
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                span.end(output={"duration_ms": round((time.perf_counter() - start) * 1000)})
                return result
            except Exception as exc:
                span.end(
                    output={"error": str(exc)},
                    level="ERROR",
                )
                raise

        return wrapper

    return decorator


# ── Tool call span ────────────────────────────────────────────────────────────

def trace_tool(name: str) -> Callable:
    """Create a Langfuse span tagged as a tool call."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            trace = kwargs.get("_trace")
            if trace is None:
                return await fn(*args, **kwargs)

            span = trace.span(name=f"tool:{name}", metadata={"tool": name})
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                span.end(output={"duration_ms": round((time.perf_counter() - start) * 1000)})
                return result
            except Exception as exc:
                span.end(output={"error": str(exc)}, level="ERROR")
                raise

        return wrapper

    return decorator
