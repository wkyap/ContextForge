"""Connector supervisor — owns running connector instances and routes to a sink."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from contextforge.connectors.base import (
    ConnectorBase,
    ConnectorStatus,
    LoggingSink,
    Record,
    Sink,
)
from contextforge.connectors.dlq import DLQRepository
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


@dataclass
class _RunningConnector:
    connector: ConnectorBase
    task: asyncio.Task[None]


class ConnectorSupervisor:
    """Manages the lifecycle of multiple named connector instances.

    A *default sink* receives records from any connector that doesn't override.
    Optional *named sinks* (registered via `register_sink`) let individual
    connectors pick a target by name (e.g. ``sink="kg"``).
    """

    def __init__(
        self,
        sink: Sink | None = None,
        *,
        dlq: DLQRepository | None = None,
    ) -> None:
        self._sink: Sink = sink or LoggingSink()
        self._sinks_by_name: dict[str, Sink] = {}
        self._sink_for_connector: dict[str, Sink] = {}
        self._sink_name_for_connector: dict[str, str] = {}
        self._running: dict[str, _RunningConnector] = {}
        self._lock = asyncio.Lock()
        self._dlq = dlq

    def register_sink(self, name: str, sink: Sink) -> None:
        """Make `sink` available for per-connector override via `sink_name`."""
        self._sinks_by_name[name] = sink
        logger.debug("Registered sink alias: %s -> %s", name, type(sink).__name__)

    def list_sinks(self) -> list[str]:
        return sorted(self._sinks_by_name.keys())

    # ── Public API ────────────────────────────────────────────────────────

    async def start(
        self,
        name: str,
        source_kind: str,
        config: dict[str, Any],
        *,
        sink_name: str | None = None,
    ) -> ConnectorBase:
        """Instantiate, connect, and begin streaming a connector by name.

        If `sink_name` is given it must match a sink registered via
        `register_sink`; that sink receives records from this connector
        instead of the supervisor default.
        """
        async with self._lock:
            if name in self._running:
                raise ValueError(f"Connector '{name}' already running")
            if sink_name is not None and sink_name not in self._sinks_by_name:
                raise KeyError(
                    f"No sink registered with name {sink_name!r}. "
                    f"Known: {sorted(self._sinks_by_name)}"
                )
            connector = get_connector_registry().instantiate(source_kind, name, config)
            if sink_name is not None:
                self._sink_for_connector[name] = self._sinks_by_name[sink_name]
                self._sink_name_for_connector[name] = sink_name
            connector._status = ConnectorStatus.STARTING  # noqa: SLF001
            try:
                await connector.connect()
            except Exception as exc:
                connector._status = ConnectorStatus.ERROR  # noqa: SLF001
                connector._last_error = str(exc)  # noqa: SLF001
                logger.exception("Connector %s failed to connect", name)
                raise
            connector._status = ConnectorStatus.RUNNING  # noqa: SLF001
            task = asyncio.create_task(self._run(connector), name=f"connector:{name}")
            self._running[name] = _RunningConnector(connector=connector, task=task)
            logger.info("Connector %s started (kind=%s)", name, source_kind)
            return connector

    async def stop(self, name: str) -> None:
        async with self._lock:
            entry = self._running.pop(name, None)
            self._sink_for_connector.pop(name, None)
            self._sink_name_for_connector.pop(name, None)
        if entry is None:
            raise KeyError(f"Connector '{name}' is not running")
        entry.connector._status = ConnectorStatus.STOPPING  # noqa: SLF001
        entry.task.cancel()
        try:
            await entry.task
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await entry.connector.close()
        except Exception:
            logger.exception("Error closing connector %s", name)
        entry.connector._status = ConnectorStatus.STOPPED  # noqa: SLF001
        logger.info("Connector %s stopped", name)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "source_kind": entry.connector.source_kind,
                "health": entry.connector.health().__dict__,
            }
            for name, entry in self._running.items()
        ]

    def get(self, name: str) -> ConnectorBase | None:
        entry = self._running.get(name)
        return entry.connector if entry else None

    async def autostart_from_registry(self, skill_registry: Any) -> int:
        """Start every `connector` SKILL with metadata.autostart == true.

        SKILL.md must declare `source_kind` (validator already requires this)
        and may provide a `config` dict in metadata. Failures are logged but
        do not crash startup.
        """
        started = 0
        for skill in skill_registry.list_by_type("connector"):
            meta = skill.metadata or {}
            if not meta.get("autostart"):
                continue
            source_kind = meta.get("source_kind")
            config = meta.get("config", {}) or {}
            if not source_kind:
                logger.warning(
                    "Connector SKILL %s has autostart=true but no source_kind", skill.name
                )
                continue
            sink_name = meta.get("sink")
            try:
                await self.start(skill.name, source_kind, config, sink_name=sink_name)
                started += 1
            except Exception:
                logger.exception(
                    "Failed to autostart connector %s (kind=%s)", skill.name, source_kind
                )
        if started:
            logger.info("Autostarted %d connector(s) from skill registry", started)
        return started

    async def autostart_from_db(self, repo: Any) -> int:
        """Start every enabled row in `connector_configs`. Failures are logged."""
        started = 0
        configs = await repo.list_all(enabled_only=True)
        for cfg in configs:
            try:
                await self.start(cfg.name, cfg.source_kind, cfg.config, sink_name=cfg.sink)
                started += 1
            except Exception:
                logger.exception(
                    "Failed to start persisted connector %s (kind=%s)",
                    cfg.name, cfg.source_kind,
                )
        if started:
            logger.info("Started %d connector(s) from connector_configs", started)
        return started

    async def shutdown(self) -> None:
        names = list(self._running.keys())
        for n in names:
            try:
                await self.stop(n)
            except Exception:
                logger.exception("Error during shutdown of %s", n)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _run(self, connector: ConnectorBase) -> None:
        sink = self._sink_for_connector.get(connector.name, self._sink)
        sink_label = self._sink_name_for_connector.get(connector.name)
        try:
            async for record in connector.stream():
                connector._mark_emitted()  # noqa: SLF001
                try:
                    await sink.write(record)
                except Exception as sink_exc:
                    logger.exception("Sink failed for record from %s", connector.name)
                    await self._dead_letter(connector.name, sink_label, record, str(sink_exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            connector._status = ConnectorStatus.ERROR  # noqa: SLF001
            connector._last_error = str(exc)  # noqa: SLF001
            logger.exception("Connector %s stream crashed", connector.name)

    async def _dead_letter(
        self,
        connector_name: str,
        sink_name: str | None,
        record: Record,
        error: str,
    ) -> None:
        """Push a failed record to the DLQ if one is configured."""
        if self._dlq is None:
            return
        try:
            await self._dlq.write(
                connector_name=connector_name,
                record=record,
                error=error,
                sink_name=sink_name,
            )
        except Exception:
            logger.exception("DLQ write itself failed for %s", connector_name)
