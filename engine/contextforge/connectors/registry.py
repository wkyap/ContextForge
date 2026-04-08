"""Connector driver registry — maps `source_kind` → driver class."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.connectors.base import ConnectorBase

logger = logging.getLogger(__name__)


class ConnectorRegistry:
    """Process-wide registry of connector driver classes keyed by source_kind."""

    def __init__(self) -> None:
        self._drivers: dict[str, type[ConnectorBase]] = {}

    def register(self, driver_cls: type[ConnectorBase]) -> None:
        kind = driver_cls.source_kind
        if not kind:
            raise ValueError(
                f"Driver {driver_cls.__name__} must declare a non-empty source_kind"
            )
        if kind in self._drivers:
            logger.warning("Replacing existing driver for source_kind=%s", kind)
        self._drivers[kind] = driver_cls
        logger.info("Registered connector driver: %s -> %s", kind, driver_cls.__name__)

    def get(self, source_kind: str) -> type[ConnectorBase] | None:
        return self._drivers.get(source_kind)

    def list_kinds(self) -> list[str]:
        return sorted(self._drivers.keys())

    def instantiate(
        self, source_kind: str, name: str, config: dict[str, Any]
    ) -> ConnectorBase:
        driver_cls = self.get(source_kind)
        if driver_cls is None:
            raise KeyError(f"No connector driver registered for source_kind={source_kind!r}")
        return driver_cls(name=name, config=config)


# Module-level singleton — drivers self-register on import.
_registry = ConnectorRegistry()


def get_connector_registry() -> ConnectorRegistry:
    return _registry


def _autoload_drivers() -> None:
    """Import built-in drivers so they self-register."""
    # Imported for side effects (registration).
    from contextforge.connectors.drivers import http_poll, mqtt  # noqa: F401


_autoload_drivers()
