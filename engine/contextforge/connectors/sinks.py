"""Built-in sinks for the connector runtime.

A `Sink` consumes records emitted by a `ConnectorBase`. The runtime fans every
record from a running connector through whichever sink the supervisor was
constructed with.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from contextforge.connectors.base import Record, Sink
from contextforge.db.neo4j import Neo4jClient
from contextforge.db.timescale import TimescaleClient

logger = logging.getLogger(__name__)


class TimescaleSink(Sink):
    """Persist records into TimescaleDB's `entity_telemetry` hypertable.

    Convention for `Record.payload`:
    - `entity_id` (str)   — required, falls back to `record.metadata['entity_id']`
                            then to `record.source`
    - `parameter` (str)   — required, falls back to `record.metadata['topic']` or 'value'
    - `value`     (number)— required
    - `unit`      (str)   — optional, default ''
    - `channel_id`(str)   — optional, default 'default'
    - `quality`   (str)   — optional, default 'valid'

    Records that cannot be coerced into a numeric value are skipped (logged at
    DEBUG). The sink is designed to be liberal: malformed records do not crash
    the connector.
    """

    def __init__(self, client: TimescaleClient) -> None:
        self._client = client
        self.written = 0
        self.skipped = 0

    async def write(self, record: Record) -> None:
        payload = record.payload or {}
        meta = record.metadata or {}

        entity_id = (
            payload.get("entity_id")
            or meta.get("entity_id")
            or record.source
        )
        parameter = (
            payload.get("parameter")
            or meta.get("topic")
            or "value"
        )
        raw_value = payload.get("value", payload.get("v"))
        try:
            value = float(raw_value) if raw_value is not None else None
        except (TypeError, ValueError):
            value = None

        if value is None:
            self.skipped += 1
            logger.debug(
                "TimescaleSink: skipping non-numeric record from %s payload=%s",
                record.source, payload,
            )
            return

        unit = str(payload.get("unit", ""))
        channel_id = str(payload.get("channel_id", "default"))
        quality = str(payload.get("quality", "valid"))
        ts = datetime.fromtimestamp(record.timestamp, tz=timezone.utc)

        try:
            await self._client.insert_telemetry(
                time=ts,
                entity_id=str(entity_id),
                channel_id=channel_id,
                parameter=str(parameter),
                value=value,
                unit=unit,
                quality=quality,
            )
            self.written += 1
        except Exception:
            self.skipped += 1
            logger.exception("TimescaleSink: insert failed for %s", record.source)

    def stats(self) -> dict[str, Any]:
        return {"written": self.written, "skipped": self.skipped}


class KGSink(Sink):
    """Persist entity-shaped records into Neo4j.

    Convention for `Record.payload`:
    - `entity_type` (str) — required (e.g. "Trainee", "Sensor", "Patient")
    - `entity_id`   (str) — required, unique within the type
    - all other keys are stored as node properties

    The sink MERGEs on (entity_type, entity_id) so it's idempotent — repeated
    records update properties in place. Records without `entity_type` are
    skipped silently (let CompositeSink route them elsewhere).
    """

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client
        self.written = 0
        self.skipped = 0

    async def write(self, record: Record) -> None:
        payload = record.payload or {}
        entity_type = payload.get("entity_type")
        entity_id = payload.get("entity_id") or (record.metadata or {}).get("entity_id")
        if not entity_type or not entity_id:
            self.skipped += 1
            return

        # Sanitize label — Cypher labels can't be parameterised.
        label = "".join(c for c in str(entity_type) if c.isalnum() or c == "_")
        if not label:
            self.skipped += 1
            return

        props = {k: v for k, v in payload.items() if k not in ("entity_type", "entity_id")}
        props["_source"] = record.source
        props["_updated_at"] = record.timestamp

        try:
            await self._client.execute_write(
                f"""
                MERGE (n:{label} {{entity_id: $entity_id}})
                SET n += $props
                """,
                {"entity_id": str(entity_id), "props": props},
            )
            self.written += 1
        except Exception:
            self.skipped += 1
            logger.exception("KGSink: MERGE failed for %s:%s", entity_type, entity_id)

    def stats(self) -> dict[str, Any]:
        return {"written": self.written, "skipped": self.skipped}


class CompositeSink(Sink):
    """Route each record to the most appropriate downstream sink.

    Routing rules (first match wins):
    1. payload has `entity_type` + `entity_id`     → KGSink
    2. payload has a numeric `value` (or `v`)      → TimescaleSink
    3. fallback                                    → LoggingSink (no-op if not set)

    The composite is the recommended default for the supervisor when both
    Neo4j and TimescaleDB are available.
    """

    def __init__(
        self,
        kg: KGSink | None = None,
        timescale: TimescaleSink | None = None,
        fallback: Sink | None = None,
    ) -> None:
        self._kg = kg
        self._ts = timescale
        self._fallback = fallback
        self.routed_kg = 0
        self.routed_ts = 0
        self.routed_fallback = 0

    async def write(self, record: Record) -> None:
        payload = record.payload or {}
        if self._kg is not None and payload.get("entity_type") and (
            payload.get("entity_id") or (record.metadata or {}).get("entity_id")
        ):
            self.routed_kg += 1
            await self._kg.write(record)
            return
        raw_value = payload.get("value", payload.get("v"))
        try:
            float(raw_value) if raw_value is not None else None
            is_numeric = raw_value is not None
        except (TypeError, ValueError):
            is_numeric = False
        if self._ts is not None and is_numeric:
            self.routed_ts += 1
            await self._ts.write(record)
            return
        if self._fallback is not None:
            self.routed_fallback += 1
            await self._fallback.write(record)

    def stats(self) -> dict[str, Any]:
        return {
            "kg": self.routed_kg,
            "timescale": self.routed_ts,
            "fallback": self.routed_fallback,
        }
