"""Retrieval router — classify queries and select retrieval strategy."""

from __future__ import annotations

import logging
from enum import StrEnum

import litellm

logger = logging.getLogger(__name__)


class RetrievalStrategy(StrEnum):
    """Available retrieval strategies."""

    LOCAL = "local"           # Entity-centric: KG neighbours + timeseries
    GLOBAL = "global"         # Community summaries for broad/thematic queries
    VECTOR = "vector"         # Pure semantic search on document chunks
    HYBRID = "hybrid"         # KG + vector combined
    TIMESERIES = "timeseries" # Time-range queries on telemetry data
    DIRECT = "direct"         # No retrieval needed (general knowledge)


_CLASSIFY_PROMPT = """Classify this user query into one retrieval strategy.

Strategies:
- local: asks about a specific entity (patient, asset, drug) — needs KG lookup
- global: broad/thematic question (trends across patients, overview of conditions) — needs community summaries
- vector: asks about documents, protocols, guidelines — needs document search
- hybrid: combines entity-specific and document knowledge
- timeseries: asks about trends, values over time, vital signs, sensor data
- direct: general knowledge question, no domain data needed

Query: {query}

Respond with ONLY the strategy name (e.g., "local")."""


async def classify_query(query: str) -> RetrievalStrategy:
    """Use an LLM to classify the query into a retrieval strategy."""
    try:
        response = await litellm.acompletion(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": _CLASSIFY_PROMPT.format(query=query)}],
            temperature=0.0,
            max_tokens=20,
        )
        raw = (response.choices[0].message.content or "").strip().lower()
        return RetrievalStrategy(raw)
    except (ValueError, Exception):
        logger.debug("Query classification fell back to hybrid for: %.80s", query)
        return RetrievalStrategy.HYBRID


def classify_query_heuristic(query: str) -> RetrievalStrategy:
    """Fast heuristic classifier (no LLM call)."""
    q = query.lower()

    ts_keywords = {"trend", "over time", "last hour", "last 24", "graph", "chart", "vitals", "readings", "sensor"}
    if any(kw in q for kw in ts_keywords):
        return RetrievalStrategy.TIMESERIES

    entity_keywords = {"patient", "who is", "tell me about", "asset", "device", "drug", "compound"}
    if any(kw in q for kw in entity_keywords):
        return RetrievalStrategy.LOCAL

    doc_keywords = {"guideline", "protocol", "policy", "document", "procedure", "how to", "sop"}
    if any(kw in q for kw in doc_keywords):
        return RetrievalStrategy.VECTOR

    global_keywords = {"overview", "summary", "across all", "distribution", "how many", "compare"}
    if any(kw in q for kw in global_keywords):
        return RetrievalStrategy.GLOBAL

    return RetrievalStrategy.HYBRID
