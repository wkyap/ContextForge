"""Budget controller — enforce token and cost limits within agent runs."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.observability.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class BudgetController:
    """Wraps CostTracker with agent-runtime integration."""

    def __init__(
        self,
        *,
        max_tokens: int = 100_000,
        max_cost_usd: float = 5.00,
        max_iterations: int = 15,
        max_tool_calls: int = 25,
    ) -> None:
        self._tracker = CostTracker(max_tokens=max_tokens, max_cost_usd=max_cost_usd)
        self._max_iterations = max_iterations
        self._max_tool_calls = max_tool_calls
        self._iterations = 0

    @property
    def tracker(self) -> CostTracker:
        return self._tracker

    def record_iteration(self) -> None:
        self._iterations += 1

    def record_llm_call(self, **kwargs: Any) -> None:
        self._tracker.record_llm_call(**kwargs)

    def record_tool_call(self) -> None:
        self._tracker.record_tool_call()

    @property
    def should_stop(self) -> bool:
        if self._tracker.over_budget:
            logger.warning("Budget exceeded: %s", self._tracker.summary())
            return True
        if self._iterations >= self._max_iterations:
            logger.warning("Iteration limit reached: %d", self._iterations)
            return True
        if self._tracker.usage.tool_calls >= self._max_tool_calls:
            logger.warning("Tool call limit reached: %d", self._tracker.usage.tool_calls)
            return True
        return False

    @property
    def stop_reason(self) -> str | None:
        if self._tracker.over_token_budget:
            return "token_budget_exceeded"
        if self._tracker.over_cost_budget:
            return "cost_budget_exceeded"
        if self._iterations >= self._max_iterations:
            return "max_iterations_reached"
        if self._tracker.usage.tool_calls >= self._max_tool_calls:
            return "max_tool_calls_reached"
        return None

    def summary(self) -> dict[str, Any]:
        return {
            **self._tracker.summary(),
            "iterations": self._iterations,
            "max_iterations": self._max_iterations,
            "max_tool_calls": self._max_tool_calls,
        }
