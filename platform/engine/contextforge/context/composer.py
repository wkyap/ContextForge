"""Context composer — assemble final context from heterogeneous sources."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compose_context(
    *,
    kg_entities: list[dict[str, Any]] | None = None,
    kg_relationships: list[dict[str, Any]] | None = None,
    document_chunks: list[dict[str, Any]] | None = None,
    timeseries_data: list[dict[str, Any]] | None = None,
    community_summaries: list[dict[str, Any]] | None = None,
    skill_context: str | None = None,
) -> str:
    """Compose a structured context string from multiple data sources.

    Sections are only included if data is present.
    """
    sections: list[str] = []

    # Skill / domain context
    if skill_context:
        sections.append(f"## Domain Knowledge\n{skill_context}")

    # Knowledge Graph entities
    if kg_entities:
        lines = ["## Entities"]
        for ent in kg_entities:
            etype = ent.get("_type", ent.get("type", "Entity"))
            name = ent.get("name", ent.get("id", "unknown"))
            props = {k: v for k, v in ent.items()
                     if not k.startswith("_") and k not in ("id", "name", "type")}
            prop_str = ", ".join(f"{k}={v}" for k, v in props.items()) if props else ""
            lines.append(f"- **{etype}**: {name}" + (f" ({prop_str})" if prop_str else ""))
        sections.append("\n".join(lines))

    # Relationships
    if kg_relationships:
        lines = ["## Relationships"]
        for rel in kg_relationships:
            lines.append(
                f"- {rel.get('type', 'RELATES_TO')}: "
                f"{rel.get('from', '?')} → {rel.get('target_id', rel.get('to', '?'))}"
            )
        sections.append("\n".join(lines))

    # Time series data
    if timeseries_data:
        lines = ["## Time Series Data"]
        for point in timeseries_data[:20]:  # Cap display
            ts = point.get("bucket", point.get("time", ""))
            val = point.get("avg_value", point.get("value", ""))
            lines.append(f"- {ts}: {val}")
        if len(timeseries_data) > 20:
            lines.append(f"  ... and {len(timeseries_data) - 20} more data points")
        sections.append("\n".join(lines))

    # Document chunks
    if document_chunks:
        lines = ["## Relevant Documents"]
        for i, chunk in enumerate(document_chunks[:10], 1):
            text = chunk.get("text", chunk.get("content", ""))[:300]
            source = chunk.get("source", "unknown")
            score = chunk.get("score", 0)
            lines.append(f"### [{i}] (source: {source}, relevance: {score:.2f})")
            lines.append(text)
        sections.append("\n".join(lines))

    # Community summaries (for global queries)
    if community_summaries:
        lines = ["## Community Overviews"]
        for cs in community_summaries[:5]:
            summary = cs.get("summary_text", cs.get("text", ""))
            members = cs.get("member_count", "?")
            lines.append(f"- **Community** ({members} members): {summary}")
        sections.append("\n".join(lines))

    if not sections:
        return "No relevant context was found for this query."

    return "\n\n".join(sections)
