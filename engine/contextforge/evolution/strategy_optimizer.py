"""Strategy Optimizer Agent — optimize retrieval strategies and prompt templates."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)


class StrategyOptimizer:
    """Analyze agent performance traces and suggest optimizations."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def analyze_performance(
        self, traces: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze a batch of traces and suggest optimizations."""
        prompt = (
            "Analyze these agent performance traces and suggest optimizations.\n"
            "Focus on: retrieval strategy selection, context quality, cost efficiency.\n\n"
            f"Traces:\n{json.dumps(traces[:20], indent=2, default=str)}\n\n"
            "Return JSON with: {\"observations\": [...], \"recommendations\": [...], \"priority\": \"high|medium|low\"}"
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            result = {"observations": [], "recommendations": [], "priority": "low"}

        logger.info("Strategy optimizer: %d recommendations", len(result.get("recommendations", [])))
        return result
