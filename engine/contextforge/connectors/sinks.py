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
