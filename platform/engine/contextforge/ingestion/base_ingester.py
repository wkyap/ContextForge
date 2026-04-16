"""Abstract base ingester — common interface, result types, and metrics."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Summary returned after an ingestion run."""

    entities_created: int = 0
    relationships_created: int = 0
    timeseries_points: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def merge(self, other: IngestResult) -> IngestResult:
        """Combine two results (e.g. after parallel sub-tasks)."""
        return IngestResult(
            entities_created=self.entities_created + other.entities_created,
            relationships_created=self.relationships_created + other.relationships_created,
            timeseries_points=self.timeseries_points + other.timeseries_points,
            errors=self.errors + other.errors,
        )


class BaseIngester(ABC):
    """Base class for all ContextForge data ingesters.

    Subclasses must implement ``ingest`` and ``validate``.  Common helpers for
    logging, timing, and error collection are provided here.
    """

    def __init__(self, *, source_name: str = "unknown") -> None:
        self._source_name = source_name
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")

    # ── Abstract interface ────────────────────────────────────────────────

    @abstractmethod
    async def ingest(self, data: Any) -> IngestResult:
        """Ingest *data* and return a result summary."""

    @abstractmethod
    async def validate(self, data: Any) -> bool:
        """Return True if *data* looks structurally valid for this ingester."""

    # ── Convenience helpers ───────────────────────────────────────────────

    async def safe_ingest(self, data: Any) -> IngestResult:
        """Validate, then ingest — catching unexpected errors."""
        start = time.monotonic()
        try:
            if not await self.validate(data):
                return IngestResult(errors=["Validation failed for incoming data"])
            result = await self.ingest(data)
        except Exception as exc:
            self._logger.exception("Ingestion failed for source=%s", self._source_name)
            return IngestResult(errors=[f"Unexpected error: {exc}"])
        elapsed = time.monotonic() - start
        self._logger.info(
            "Ingestion complete — source=%s entities=%d rels=%d ts=%d errors=%d (%.2fs)",
            self._source_name,
            result.entities_created,
            result.relationships_created,
            result.timeseries_points,
            len(result.errors),
            elapsed,
        )
        return result
