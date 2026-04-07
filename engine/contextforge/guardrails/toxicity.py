"""Toxicity detection guardrail — flag harmful, dangerous, or discriminatory content."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern categories for toxic / unsafe content.
# Each maps a category name to a list of compiled regex patterns.
# ---------------------------------------------------------------------------

_HARMFUL_MEDICAL: list[re.Pattern] = [
    re.compile(r"\b(?:stop\s+(?:taking|using)\s+(?:your\s+)?(?:medication|insulin|chemo|prescribed))", re.IGNORECASE),
    re.compile(r"\b(?:don'?t\s+(?:see|visit|consult)\s+(?:a\s+)?(?:doctor|physician|specialist))", re.IGNORECASE),
    re.compile(r"\b(?:cure[sd]?\s+(?:cancer|diabetes|HIV|AIDS))\b", re.IGNORECASE),
    re.compile(r"\b(?:inject|ingest|consume)\s+(?:bleach|disinfectant|chlorine)", re.IGNORECASE),
    re.compile(r"\b(?:essential\s+oils?\s+(?:cure|treat|heal))", re.IGNORECASE),
]

_DANGEROUS_INSTRUCTIONS: list[re.Pattern] = [
    re.compile(r"\b(?:how\s+to\s+(?:make|build|create)\s+(?:a\s+)?(?:bomb|explosive|weapon))", re.IGNORECASE),
    re.compile(r"\b(?:synthesiz(?:e|ing)\s+(?:drugs|meth|fentanyl))", re.IGNORECASE),
    re.compile(r"\b(?:instructions?\s+(?:for|to)\s+(?:hack|breach|exploit))", re.IGNORECASE),
    re.compile(r"\b(?:bypass\s+(?:security|firewall|authentication))\b", re.IGNORECASE),
    re.compile(r"\b(?:how\s+to\s+(?:pick|crack)\s+(?:a\s+)?lock)", re.IGNORECASE),
]

_DISCRIMINATORY: list[re.Pattern] = [
    re.compile(r"\b(?:all\s+(?:\w+\s+)?(?:people|men|women)\s+are\s+(?:stupid|inferior|worthless))", re.IGNORECASE),
    re.compile(r"\b(?:(?:race|gender|religion)\s+(?:is\s+)?(?:superior|inferior))", re.IGNORECASE),
    re.compile(r"\b(?:should(?:n'?t)?\s+(?:be\s+)?(?:allowed|permitted)\s+to\s+(?:vote|work|live))", re.IGNORECASE),
    re.compile(r"\b(?:go\s+back\s+to\s+(?:your|their)\s+country)", re.IGNORECASE),
]

_CATEGORIES: dict[str, list[re.Pattern]] = {
    "harmful_medical_advice": _HARMFUL_MEDICAL,
    "dangerous_instructions": _DANGEROUS_INSTRUCTIONS,
    "discriminatory_content": _DISCRIMINATORY,
}


@dataclass
class ToxicityResult:
    """Result of a toxicity check."""

    passed: bool
    score: float  # 0.0 = clean, 1.0 = highly toxic
    details: str


async def check_toxicity(text: str) -> ToxicityResult:
    """Check text for toxic or harmful content using pattern matching.

    Returns a ``ToxicityResult`` with a score between 0 and 1 and a
    human-readable summary of any matches found.
    """
    if not text:
        return ToxicityResult(passed=True, score=0.0, details="Empty input")

    matches: list[str] = []

    for category, patterns in _CATEGORIES.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                matches.append(f"{category}: '{match.group()}'")

    if not matches:
        return ToxicityResult(passed=True, score=0.0, details="No toxic content detected")

    # Score rises with the number of distinct matches, capped at 1.0.
    score = min(len(matches) * 0.25, 1.0)
    detail_text = f"Detected {len(matches)} issue(s): " + "; ".join(matches)

    logger.warning("Toxicity detected: %s", detail_text)
    return ToxicityResult(passed=False, score=score, details=detail_text)
