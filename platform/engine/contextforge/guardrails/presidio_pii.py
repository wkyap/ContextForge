"""Presidio-based PII detection — multilingual NER on top of regex.

This is opt-in via the `CONTEXTFORGE_PRESIDIO_ENABLED` setting. The Presidio
engines (and their underlying spaCy model) are large, so we lazy-init them
once on first use to avoid paying the cost at import time.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_analyzer: Any | None = None
_anonymizer: Any | None = None
_init_lock = Lock()
_init_failed = False


def _ensure_engines() -> tuple[Any | None, Any | None]:
    """Lazily import and initialise Presidio engines. Returns (analyzer, anonymizer)."""
    global _analyzer, _anonymizer, _init_failed
    if _init_failed:
        return None, None
    if _analyzer is not None and _anonymizer is not None:
        return _analyzer, _anonymizer
    with _init_lock:
        if _analyzer is not None and _anonymizer is not None:
            return _analyzer, _anonymizer
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            _analyzer = AnalyzerEngine()
            _anonymizer = AnonymizerEngine()
            logger.info("Presidio engines initialised")
        except Exception:
            logger.warning(
                "Presidio not available — falling back to regex PII only", exc_info=True
            )
            _init_failed = True
            return None, None
    return _analyzer, _anonymizer


@dataclass
class PresidioResult:
    found: bool = False
    detections: list[dict[str, Any]] = field(default_factory=list)
    redacted_text: str = ""


def detect_and_anonymize(text: str, language: str = "en") -> PresidioResult:
    """Run Presidio analyzer + anonymizer on text. Safe no-op if Presidio absent."""
    analyzer, anonymizer = _ensure_engines()
    if analyzer is None or anonymizer is None:
        return PresidioResult(redacted_text=text)

    try:
        analyzer_results = analyzer.analyze(text=text, language=language)
    except Exception:
        logger.warning("Presidio analyze failed", exc_info=True)
        return PresidioResult(redacted_text=text)

    if not analyzer_results:
        return PresidioResult(redacted_text=text)

    try:
        anonymized = anonymizer.anonymize(text=text, analyzer_results=analyzer_results)
        redacted = anonymized.text
    except Exception:
        logger.warning("Presidio anonymize failed", exc_info=True)
        redacted = text

    detections = [
        {
            "type": r.entity_type,
            "score": float(r.score),
            "position": f"{r.start}-{r.end}",
        }
        for r in analyzer_results
    ]
    return PresidioResult(found=True, detections=detections, redacted_text=redacted)
