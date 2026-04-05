"""Context pruner — re-rank and prune retrieved chunks by relevance."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def prune_by_score(
    chunks: list[dict[str, Any]],
    *,
    min_score: float = 0.3,
    max_chunks: int = 20,
    score_key: str = "score",
) -> list[dict[str, Any]]:
    """Drop chunks below the score threshold and cap the count."""
    filtered = [c for c in chunks if c.get(score_key, 0) >= min_score]
    filtered.sort(key=lambda c: c.get(score_key, 0), reverse=True)
    pruned = filtered[:max_chunks]
    logger.debug(
        "Pruned %d → %d chunks (min_score=%.2f, max=%d)",
        len(chunks), len(pruned), min_score, max_chunks,
    )
    return pruned


def deduplicate(
    chunks: list[dict[str, Any]],
    *,
    key: str = "text",
    similarity_threshold: float = 0.95,
) -> list[dict[str, Any]]:
    """Remove near-duplicate chunks based on text overlap."""
    seen: list[str] = []
    unique: list[dict[str, Any]] = []

    for chunk in chunks:
        text = chunk.get(key, "")
        is_dup = False
        for s in seen:
            overlap = _jaccard_similarity(text, s)
            if overlap >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(chunk)
            seen.append(text)

    if len(unique) < len(chunks):
        logger.debug("Deduplication removed %d chunks", len(chunks) - len(unique))
    return unique


def _jaccard_similarity(a: str, b: str) -> float:
    """Quick word-level Jaccard similarity."""
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
