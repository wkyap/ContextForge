"""Quality Improvement Agent — assess and improve response quality."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)


class QualityImprover:
    """Evaluate agent responses and generate improvement proposals."""

    def __init__(self, *, model: str = "openai/gpt-4o") -> None:
        self._model = model

    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: str,
    ) -> dict[str, Any]:
        """Score and evaluate a single agent response."""
        prompt = (
            "Evaluate this AI assistant response on these dimensions (1-5 each):\n"
            "- relevance: Does it answer the question?\n"
            "- accuracy: Is the information correct based on the context?\n"
            "- completeness: Does it cover all aspects?\n"
            "- conciseness: Is it appropriately concise?\n"
            "- safety: Does it avoid harmful or unsupported claims?\n\n"
            f"Query: {query}\n\n"
            f"Context provided:\n{context[:2000]}\n\n"
            f"Response:\n{response}\n\n"
            "Return JSON: {\"scores\": {\"relevance\": N, ...}, \"overall\": N, "
            "\"issues\": [...], \"suggestions\": [...]}"
        )

        result = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        raw = result.choices[0].message.content or "{}"
        try:
            evaluation: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            evaluation = {"scores": {}, "overall": 0, "issues": [], "suggestions": []}

        return evaluation

    async def generate_improvement_proposal(
        self, evaluations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Aggregate evaluations into a system improvement proposal."""
        prompt = (
            "Based on these response quality evaluations, propose system improvements.\n\n"
            f"Evaluations:\n{json.dumps(evaluations[:10], indent=2, default=str)}\n\n"
            "Return JSON: {\"proposal_type\": \"prompt_revision|guardrails_adjustment|strategy_optimization\", "
            "\"title\": \"...\", \"description\": \"...\", \"changes\": [...], \"expected_impact\": \"...\"}"
        )

        result = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = result.choices[0].message.content or "{}"
        try:
            proposal: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            proposal = {"proposal_type": "unknown", "title": "Parse error", "changes": []}
        return proposal
