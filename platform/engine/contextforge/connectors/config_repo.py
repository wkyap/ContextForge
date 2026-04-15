"""Repository for persisted connector configurations (postgres-backed)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from contextforge.db.postgres import PostgresClient

logger = logging.getLogger(__name__)


@dataclass
class ConnectorConfig:
    name: str
    source_kind: str
    config: dict[str, Any]
    sink: str | None
    enabled: bool
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_kind": self.source_kind,
            "config": self.config,
            "sink": self.sink,
            "enabled": self.enabled,
            "description": self.description,
        }


class ConnectorConfigRepo:
    """CRUD over the `connector_configs` table."""

    def __init__(self, postgres: PostgresClient) -> None:
        self._pg = postgres

    @staticmethod
    def _row_to_cfg(row: Any) -> ConnectorConfig:
        cfg_raw = row["config"]
        cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})
        return ConnectorConfig(
            name=row["name"],
            source_kind=row["source_kind"],
            config=cfg,
            sink=row["sink"],
            enabled=row["enabled"],
            description=row["description"],
        )

    async def upsert(self, cfg: ConnectorConfig) -> ConnectorConfig:
        await self._pg.execute(
            """
            INSERT INTO connector_configs (name, source_kind, config, sink, enabled, description)
            VALUES ($1, $2, $3::jsonb, $4, $5, $6)
            ON CONFLICT (name) DO UPDATE
                SET source_kind = EXCLUDED.source_kind,
                    config      = EXCLUDED.config,
                    sink        = EXCLUDED.sink,
                    enabled     = EXCLUDED.enabled,
                    description = EXCLUDED.description,
                    updated_at  = NOW()
            """,
            cfg.name, cfg.source_kind, json.dumps(cfg.config),
            cfg.sink, cfg.enabled, cfg.description,
        )
        return cfg

    async def get(self, name: str) -> ConnectorConfig | None:
        row = await self._pg.fetchrow(
            "SELECT name, source_kind, config, sink, enabled, description "
            "FROM connector_configs WHERE name = $1",
            name,
        )
        return self._row_to_cfg(row) if row else None

    async def list_all(self, *, enabled_only: bool = False) -> list[ConnectorConfig]:
        query = (
            "SELECT name, source_kind, config, sink, enabled, description "
            "FROM connector_configs"
        )
        if enabled_only:
            query += " WHERE enabled = TRUE"
        query += " ORDER BY name"
        rows = await self._pg.fetch(query)
        return [self._row_to_cfg(r) for r in rows]

    async def delete(self, name: str) -> bool:
        result = await self._pg.execute(
            "DELETE FROM connector_configs WHERE name = $1", name
        )
        return result.endswith(" 1")
