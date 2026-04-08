"""Connector base classes — foundation for the Phase 2 ingestion runtime.

A `Connector` is a long-lived (or batch) source of records that streams into the
ingestion pipeline. The runtime supervises one instance per active configuration
and routes records to a `Sink`.

Drivers subclass `ConnectorBase` and are matched to `connector` SKILL.md entries
by their declared `source_kind` (e.g. "messaging", "database", "api").
"""

from __future__ import annotations

import abc
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConnectorStatus(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class Record:
    """A single record yielded by a connector."""

    payload: dict[str, Any]
    source: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorHealth:
    status: ConnectorStatus
    records_emitted: int = 0
    last_record_at: float | None = None
    last_error: str | None = None


class ConnectorBase(abc.ABC):
    """Abstract base for all connector drivers.

    Subclasses must implement `connect`, `stream`, and `close`. Drivers should
    NOT push to sinks directly — that's the runtime's job. They simply yield
    `Record` objects from `stream()`.
    """

    #: The `source_kind` value this driver handles. Drivers register themselves
    #: with the connector registry via this attribute.
    source_kind: str = ""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self._status = ConnectorStatus.IDLE
        self._records_emitted = 0
        self._last_record_at: float | None = None
        self._last_error: str | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    @abc.abstractmethod
    async def connect(self) -> None:
        """Open the underlying connection. Raises on failure."""

    @abc.abstractmethod
    async def stream(self) -> AsyncIterator[Record]:
        """Yield records from the source. Should run until cancelled."""
        # The yield is here so type checkers see this as an async generator.
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down the connection. Must be idempotent."""

    # ── Health ────────────────────────────────────────────────────────────

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            status=self._status,
            records_emitted=self._records_emitted,
            last_record_at=self._last_record_at,
            last_error=self._last_error,
        )

    # ── Internal hooks ────────────────────────────────────────────────────

    def _mark_emitted(self) -> None:
        self._records_emitted += 1
        self._last_record_at = time.time()


class Sink(abc.ABC):
    """Where records go after a connector emits them."""

    @abc.abstractmethod
    async def write(self, record: Record) -> None: ...

    async def close(self) -> None:  # default no-op
        return None


class LoggingSink(Sink):
    """Default sink — logs each record at INFO. Useful for smoke testing."""

    def __init__(self, prefix: str = "ingest") -> None:
        self.prefix = prefix
        self.count = 0

    async def write(self, record: Record) -> None:
        self.count += 1
        logger.info(
            "[%s] record from %s ts=%.3f payload=%s",
            self.prefix,
            record.source,
            record.timestamp,
            record.payload,
        )
