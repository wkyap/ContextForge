"""Hallucination detection guardrail — verify claims against retrieved context."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import litellm

logger = logging.getLogger(__name__)

_CHECK_PROMPT = """You are a fact-checking system. Given the AI's response and the source context
it was based on, identify any claims in the response that are NOT supported by the context.

Context:
{context}

AI Response:
{response}

List each unsupported claim on a new line starting with "- UNSUPPORTED: ".
If all claims are supported, respond with "ALL_SUPPORTED".
"""


@dataclass
class HallucinationResult:
    passed: bool
    unsupported_claims: list[str]
    confidence: float  # 0-1, how confident we are in the check


async def check_hallucination(
    response: str,
    context: str,
    *,
    model: str = "openai/gpt-4o-mini",
) -> HallucinationResult:
    """Check an AI response for hallucinated claims not in the source context."""
    if not context or not response:
        return HallucinationResult(passed=True, unsupported_claims=[], confidence=0.5)

    try:
        result = await litellm.acompletion(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": _CHECK_PROMPT.format(
                        context=context, response=response,
                    ),
                },
            ],
            temperature=0.0,
            max_tokens=500,
        )
        text = result.choices[0].message.content or ""

        if "ALL_SUPPORTED" in text:
            return HallucinationResult(passed=True, unsupported_claims=[], confidence=0.9)

        claims = [
            line.replace("- UNSUPPORTED:", "").strip()
            for line in text.splitlines()
            if "UNSUPPORTED" in line
        ]
        return HallucinationResult(
            passed=len(claims) == 0,
            unsupported_claims=claims,
            confidence=0.8,
        )
    except Exception:
        logger.warning("Hallucination check failed", exc_info=True)
        return HallucinationResult(passed=True, unsupported_claims=[], confidence=0.0)
