"""PII / PHI detection guardrail."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Common PII patterns (UK + US focused).
_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_uk": re.compile(r"\b(?:0|\+44)\d{10,11}\b"),
    "phone_us": re.compile(r"\b(?:\+1)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "nhs_number": re.compile(r"\b\d{3}\s?\d{3}\s?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    "date_of_birth": re.compile(
        r"\b(?:DOB|dob|Date of Birth)[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    ),
    "mrn": re.compile(r"\bMRN[-:\s]*[A-Z0-9]{5,15}\b", re.IGNORECASE),
}


@dataclass
class PIIDetection:
    found: bool = False
    detections: list[dict[str, str]] = field(default_factory=list)
    redacted_text: str = ""


def detect_pii(text: str) -> PIIDetection:
    """Scan text for PII patterns."""
    result = PIIDetection(redacted_text=text)

    for pii_type, pattern in _PATTERNS.items():
        for match in pattern.finditer(text):
            result.found = True
            result.detections.append({
                "type": pii_type,
                "value": match.group()[:4] + "***",
                "position": f"{match.start()}-{match.end()}",
            })
            # Redact in output
            result.redacted_text = result.redacted_text.replace(
                match.group(), f"[{pii_type.upper()}_REDACTED]"
            )

    if result.found:
        logger.warning("PII detected: %d instances", len(result.detections))
    return result


def redact_pii(text: str) -> str:
    """Return text with all detected PII redacted."""
    return detect_pii(text).redacted_text
