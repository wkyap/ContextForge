"""Error recovery — retry, fallback, and graceful degradation for agent runs."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base error for agent runtime failures."""

    def __init__(self, message: str, *, recoverable: bool = True) -> None:
        super().__init__(message)
        self.recoverable = recoverable


class ToolExecutionError(AgentError):
    """A tool call failed."""
    pass


class LLMCallError(AgentError):
    """An LLM call failed."""
    pass


class BudgetExceededError(AgentError):
    """Budget limits were exceeded."""

    def __init__(self, message: str = "Budget exceeded") -> None:
        super().__init__(message, recoverable=False)


# ── Retry decorator for LLM calls ────────────────────────────────────────────

def with_llm_retry(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Retry LLM calls with exponential backoff."""
    return retry(
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=lambda rs: logger.warning(
            "LLM call failed (attempt %d), retrying...", rs.attempt_number
        ),
    )(fn)


# ── Fallback model chain ─────────────────────────────────────────────────────

async def call_with_fallback(
    models: list[str],
    messages: list[dict[str, str]],
    call_fn: Any,
    **kwargs: Any,
) -> Any:
    """Try models in order until one succeeds."""
    last_error: Exception | None = None
    for model in models:
        try:
            return await call_fn(model=model, messages=messages, **kwargs)
        except Exception as exc:
            logger.warning("Model %s failed: %s — trying next", model, exc)
            last_error = exc
    raise LLMCallError(
        f"All models failed: {[m for m in models]}. Last error: {last_error}"
    )


# ── Recovery strategies ───────────────────────────────────────────────────────

def build_error_message(error: Exception) -> str:
    """Create a user-friendly error message from an agent exception."""
    if isinstance(error, BudgetExceededError):
        return "I've reached my processing budget for this request. Here's what I found so far."
    if isinstance(error, ToolExecutionError):
        return f"A tool encountered an error: {error}. I'll try to answer without it."
    if isinstance(error, LLMCallError):
        return "I'm having trouble connecting to the AI service. Please try again shortly."
    return "An unexpected error occurred. Please try again."
