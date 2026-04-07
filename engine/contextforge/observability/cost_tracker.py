"""Per-run token usage and cost tracking.

Accumulates token counts across multiple LLM calls within a single agent
run, then writes a summary to Langfuse and optionally enforces budget caps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RunUsage:
    """Mutable accumulator for a single agent run."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0


class CostTracker:
    """Tracks token budget for one agent run."""

    def __init__(
        self,
        *,
        max_tokens: int = 100_000,
        max_cost_usd: float = 5.00,
    ) -> None:
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd
        self.usage = RunUsage()

    # ── Recording ─────────────────────────────────────────────────────────

    def record_llm_call(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        self.usage.prompt_tokens += prompt_tokens
        self.usage.completion_tokens += completion_tokens
        self.usage.total_tokens += prompt_tokens + completion_tokens
        self.usage.estimated_cost_usd += cost_usd
        self.usage.llm_calls += 1

    def record_tool_call(self) -> None:
        self.usage.tool_calls += 1

    # ── Budget checks ─────────────────────────────────────────────────────

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.max_tokens - self.usage.total_tokens)

    @property
    def budget_remaining_usd(self) -> float:
        return max(0.0, self.max_cost_usd - self.usage.estimated_cost_usd)

    @property
    def over_token_budget(self) -> bool:
        return self.usage.total_tokens >= self.max_tokens

    @property
    def over_cost_budget(self) -> bool:
        return self.usage.estimated_cost_usd >= self.max_cost_usd

    @property
    def over_budget(self) -> bool:
        return self.over_token_budget or self.over_cost_budget

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            "prompt_tokens": self.usage.prompt_tokens,
            "completion_tokens": self.usage.completion_tokens,
            "total_tokens": self.usage.total_tokens,
            "estimated_cost_usd": round(self.usage.estimated_cost_usd, 6),
            "llm_calls": self.usage.llm_calls,
            "tool_calls": self.usage.tool_calls,
            "over_budget": self.over_budget,
        }
