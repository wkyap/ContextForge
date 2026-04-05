"""Singapore PDPA PII detection and masking guardrail.

Covers NRIC/FIN, Singapore phone numbers, and email addresses
per the Feb 2026 PDPC directive on NRIC usage.
"""

from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Singapore-specific PII patterns
_SG_PATTERNS: dict[str, re.Pattern] = {
    "sg_nric": re.compile(r"\b[STFGM]\d{7}[A-Z]\b"),
    "sg_phone": re.compile(r"\b[689]\d{7}\b"),
    "sg_phone_prefix": re.compile(r"\b\+65\s?[689]\d{7}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "uen": re.compile(r"\b\d{8,9}[A-Z]\b"),  # Singapore Unique Entity Number
}

# Masking formats per PII type
_MASK_FORMATS: dict[str, str] = {
    "sg_nric": "****{last4}",
    "sg_phone": "****{last4}",
    "sg_phone_prefix": "+65 ****{last4}",
    "email": "[EMAIL_REDACTED]",
    "credit_card": "[CARD_REDACTED]",
    "uen": None,  # UEN is public business data, no masking needed
}


@dataclass
class PDPADetection:
    found: bool = False
    detections: list[dict[str, str]] = field(default_factory=list)
    redacted_text: str = ""
    severity: str = "pass"  # pass, warn, block


def _mask_value(pii_type: str, value: str) -> str:
    """Apply masking format to a PII value."""
    fmt = _MASK_FORMATS.get(pii_type)
    if fmt is None:
        return value  # no masking (e.g., UEN)
    if "{last4}" in fmt:
        return fmt.replace("{last4}", value[-4:])
    return fmt


def detect_pdpa_pii(text: str) -> PDPADetection:
    """Scan text for Singapore PDPA-regulated PII."""
    result = PDPADetection(redacted_text=text)

    for pii_type, pattern in _SG_PATTERNS.items():
        if pii_type == "uen":
            continue  # UEN is public data

        for match in pattern.finditer(text):
            result.found = True
            masked = _mask_value(pii_type, match.group())
            result.detections.append({
                "type": pii_type,
                "masked": masked,
                "position": f"{match.start()}-{match.end()}",
            })
            result.redacted_text = result.redacted_text.replace(
                match.group(), masked
            )

    if result.found:
        # NRIC or credit card = block severity
        pii_types = {d["type"] for d in result.detections}
        if pii_types & {"sg_nric", "credit_card"}:
            result.severity = "block"
        else:
            result.severity = "warn"
        logger.warning(
            "PDPA PII detected: %d instances (severity=%s)",
            len(result.detections),
            result.severity,
        )

    return result


def redact_pdpa(text: str) -> str:
    """Return text with all PDPA-regulated PII masked."""
    return detect_pdpa_pii(text).redacted_text


def hash_nric(nric: str) -> str:
    """SHA-256 hash an NRIC for storage. Never store raw."""
    return hashlib.sha256(nric.strip().upper().encode()).hexdigest()


def mask_nric_display(nric: str) -> str:
    """Mask NRIC for display: S****567A."""
    if len(nric) >= 9:
        return nric[0] + "****" + nric[-4:]
    return "****"


def mask_phone(phone: str) -> str:
    """Mask phone to last 4 digits."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) >= 4:
        return "****" + digits[-4:]
    return "****"
