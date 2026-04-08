"""Connector supervisor — owns running connector instances and routes to a sink."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from contextforge.connectors.base import ConnectorBase, ConnectorStatus, LoggingSink, Sink
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


@dataclass
class _RunningConnector:
    connector: ConnectorBase
    task: asyncio.Task[None]


class ConnectorSupervisor:
    """Manages the lifecycle of multiple named connector instances."""

    def __init__(self, sink: Sink | None = None) -> None:
        self._sink: Sink = sink or LoggingSink()
        self._running: dict[str, _RunningConnector] = {}
        self._lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    async def start(
        self, name: str, source_kind: str, config: dict[str, Any]
    ) -> ConnectorBase:
        """Instantiate, connect, and begin streaming a connector by name."""
        async with self._lock:
            if name in self._running:
                raise ValueError(f"Connector '{name}' already running")
            connector = get_connector_registry().instantiate(source_kind, name, config)
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

    async def shutdown(self) -> None:
        names = list(self._running.keys())
        for n in names:
            try:
                await self.stop(n)
            except Exception:
                logger.exception("Error during shutdown of %s", n)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _run(self, connector: ConnectorBase) -> None:
        try:
            async for record in connector.stream():
                connector._mark_emitted()  # noqa: SLF001
                try:
                    await self._sink.write(record)
                except Exception:
                    logger.exception("Sink failed for record from %s", connector.name)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            connector._status = ConnectorStatus.ERROR  # noqa: SLF001
            connector._last_error = str(exc)  # noqa: SLF001
            logger.exception("Connector %s stream crashed", connector.name)
