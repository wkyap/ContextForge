"""Stream ingester — Redis Streams consumer for real-time MQTT/Kafka-style messages."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from contextforge.db.redis import RedisClient
from contextforge.db.timescale import TimescaleClient
from contextforge.knowledge.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)

# Messages with these keys are treated as numeric telemetry.
_NUMERIC_KEYS = {"value", "reading", "measurement"}

# Consumer group name for ContextForge stream processing.
_CONSUMER_GROUP = "contextforge_ingest"


class StreamIngester:
    """Consume real-time data from Redis Streams and route to the appropriate store.

    Numeric telemetry (values with a float ``value`` field) is routed to
    TimescaleDB.  Events and entity updates are routed to the Neo4j-backed
    temporal knowledge graph.
    """

    def __init__(
        self,
        redis: RedisClient,
        timescale: TimescaleClient,
        graph: TemporalGraph,
        *,
        consumer_name: str = "worker-1",
        batch_size: int = 100,
        block_ms: int = 2000,
    ) -> None:
        self._redis = redis
        self._timescale = timescale
        self._graph = graph
        self._consumer_name = consumer_name
        self._batch_size = batch_size
        self._block_ms = block_ms
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────

    async def start_consuming(self, stream_key: str) -> None:
        """Begin consuming messages from *stream_key* in a loop.

        This method blocks until ``stop()`` is called.  It automatically
        creates the consumer group if it does not already exist.
        """
        await self._ensure_consumer_group(stream_key)
        self._running = True
        logger.info(
            "StreamIngester started — stream=%s consumer=%s",
            stream_key,
            self._consumer_name,
        )

        while self._running:
            try:
                messages = await self._redis.client.xreadgroup(
                    groupname=_CONSUMER_GROUP,
                    consumername=self._consumer_name,
                    streams={stream_key: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
                if not messages:
                    continue

                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        try:
                            await self.process_message(fields)
                            await self._redis.client.xack(
                                stream_key, _CONSUMER_GROUP, msg_id
                            )
                        except Exception:
                            logger.exception(
                                "Failed to process message %s", msg_id
                            )
            except asyncio.CancelledError:
                logger.info("StreamIngester cancelled — shutting down")
                break
            except Exception:
                logger.exception("Stream read error — retrying in 1s")
                await asyncio.sleep(1)

        logger.info("StreamIngester stopped")

    def stop(self) -> None:
        """Signal the consumer loop to exit after the current batch."""
        self._running = False

    async def process_message(self, msg: dict[str, Any]) -> None:
        """Route a single message to the correct data store.

        Messages whose payload contains a numeric ``value`` (or ``reading`` /
        ``measurement``) key are inserted into TimescaleDB.  All other
        messages are treated as entity-creation events and sent to the
        temporal knowledge graph.
        """
        # Try to deserialise a JSON payload if present.
        payload = msg
        if "payload" in msg:
            try:
                payload = json.loads(msg["payload"])
            except (json.JSONDecodeError, TypeError):
                payload = msg

        if self._is_telemetry(payload):
            await self._route_to_timescale(payload)
        else:
            await self._route_to_graph(payload)

    # ── Internal routing ──────────────────────────────────────────────────

    @staticmethod
    def _is_telemetry(payload: dict[str, Any]) -> bool:
        """Return True if the payload looks like numeric telemetry."""
        for key in _NUMERIC_KEYS:
            val = payload.get(key)
            if val is not None:
                try:
                    float(val)
                    return True
                except (ValueError, TypeError):
                    pass
        return False

    async def _route_to_timescale(self, payload: dict[str, Any]) -> None:
        """Insert a numeric telemetry reading into TimescaleDB."""
        # Determine the numeric value from the first matching key.
        value: float = 0.0
        for key in _NUMERIC_KEYS:
            raw = payload.get(key)
            if raw is not None:
                try:
                    value = float(raw)
                    break
                except (ValueError, TypeError):
                    continue

        time_str = payload.get("time") or payload.get("timestamp")
        if time_str:
            ts = datetime.fromisoformat(str(time_str))
        else:
            ts = datetime.now(timezone.utc)

        await self._timescale.insert_telemetry(
            time=ts,
            entity_id=str(payload.get("entity_id", "")),
            channel_id=str(payload.get("channel_id", "")),
            parameter=str(payload.get("parameter", payload.get("metric", "unknown"))),
            value=value,
            unit=str(payload.get("unit", "")),
            quality=str(payload.get("quality", "valid")),
        )
        logger.debug("Telemetry routed to TimescaleDB: entity=%s", payload.get("entity_id"))

    async def _route_to_graph(self, payload: dict[str, Any]) -> None:
        """Create or update an entity in the temporal knowledge graph."""
        entity_type = str(payload.pop("entity_type", payload.pop("type", "Event")))
        source_id = str(payload.get("id", payload.get("source_id", "")))

        await self._graph.create_entity(
            entity_type=entity_type,
            properties=payload,
            source_system="stream",
            source_id=source_id,
            changed_by="stream_ingester",
        )
        logger.debug("Event/entity routed to graph: type=%s id=%s", entity_type, source_id)

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _ensure_consumer_group(self, stream_key: str) -> None:
        """Create the consumer group if it doesn't already exist."""
        try:
            await self._redis.client.xgroup_create(
                stream_key, _CONSUMER_GROUP, id="0", mkstream=True
            )
            logger.info("Created consumer group '%s' on stream '%s'", _CONSUMER_GROUP, stream_key)
        except Exception:
            # Group already exists — that's fine.
            logger.debug("Consumer group '%s' already exists", _CONSUMER_GROUP)
