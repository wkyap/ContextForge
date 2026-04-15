"""Provenance guardrail — track and verify source attribution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SourceAttribution:
    """A single source reference."""

    source_type: str  # "kg_entity", "document", "timeseries", "community"
    source_id: str
    description: str
    confidence: float = 1.0


@dataclass
class ProvenanceRecord:
    """Complete provenance for an agent response."""

    sources: list[SourceAttribution] = field(default_factory=list)
    retrieval_strategy: str = ""
    context_tokens: int = 0
    compressed: bool = False

    def add_kg_source(self, entity_id: str, entity_type: str, name: str) -> None:
        self.sources.append(SourceAttribution(
            source_type="kg_entity",
            source_id=entity_id,
            description=f"{entity_type}: {name}",
        ))

    def add_document_source(
        self, doc_id: str, source: str, score: float
    ) -> None:
        self.sources.append(SourceAttribution(
            source_type="document",
            source_id=doc_id,
            description=f"Document from {source}",
            confidence=score,
        ))

    def add_timeseries_source(
        self, entity_id: str, parameter: str, data_points: int
    ) -> None:
        self.sources.append(SourceAttribution(
            source_type="timeseries",
            source_id=entity_id,
            description=f"{parameter}: {data_points} data points",
        ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [
                {
                    "type": s.source_type,
                    "id": s.source_id,
                    "description": s.description,
                    "confidence": s.confidence,
                }
                for s in self.sources
            ],
            "retrieval_strategy": self.retrieval_strategy,
            "context_tokens": self.context_tokens,
            "compressed": self.compressed,
            "source_count": len(self.sources),
        }

    @property
    def has_sources(self) -> bool:
        return len(self.sources) > 0
