"""Built-in sinks for the connector runtime.

A `Sink` consumes records emitted by a `ConnectorBase`. The runtime fans every
record from a running connector through whichever sink the supervisor was
constructed with.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from contextforge.connectors.base import Record, Sink
from contextforge.db.neo4j import Neo4jClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.timescale import TimescaleClient
from contextforge.knowledge.embedding_service import EmbeddingService

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


class VectorSink(Sink):
    """Embed text-shaped records and upsert into a Qdrant collection.

    Convention for `Record.payload`:
    - `text` (str)            — required source text to embed
    - `doc_id` (str)          — optional stable id; defaults to uuid4
    - everything else becomes Qdrant point payload (alongside `text`, `_source`)

    Embedding goes through the project's `EmbeddingService` (LiteLLM gateway).
    Records without `text` are skipped.
    """

    def __init__(
        self,
        qdrant: QdrantClient,
        embedder: EmbeddingService,
        collection: str = "document_chunks",
    ) -> None:
        self._qdrant = qdrant
        self._embedder = embedder
        self._collection = collection
        self.written = 0
        self.skipped = 0

    async def write(self, record: Record) -> None:
        from qdrant_client.models import PointStruct

        payload = record.payload or {}
        text = payload.get("text")
        if not text or not isinstance(text, str):
            self.skipped += 1
            return
        try:
            vector = await self._embedder.embed(text)
        except Exception:
            self.skipped += 1
            logger.exception("VectorSink: embedding failed for %s", record.source)
            return

        point_payload = {k: v for k, v in payload.items() if k != "text"}
        point_payload["text"] = text
        point_payload["_source"] = record.source
        point_payload["_updated_at"] = record.timestamp

        doc_id = str(payload.get("doc_id") or uuid.uuid4())
        try:
            await self._qdrant.upsert(
                self._collection,
                [PointStruct(id=doc_id, vector=vector, payload=point_payload)],
            )
            self.written += 1
        except Exception:
            self.skipped += 1
            logger.exception("VectorSink: upsert failed for %s", record.source)

    def stats(self) -> dict[str, Any]:
        return {"written": self.written, "skipped": self.skipped}


class FanOutSink(Sink):
    """Write each record to multiple sinks concurrently.

    Use when a record is meaningful to more than one store — e.g. an entity
    record with telemetry should land in both Neo4j (KGSink) and TimescaleDB
    (TimescaleSink). Failures in any one sink are isolated; other sinks still
    receive the record.
    """

    def __init__(self, sinks: list[Sink]) -> None:
        self._sinks = sinks

    async def write(self, record: Record) -> None:
        results = await asyncio.gather(
            *(s.write(record) for s in self._sinks), return_exceptions=True
        )
        for sink, res in zip(self._sinks, results, strict=False):
            if isinstance(res, Exception):
                logger.warning("FanOutSink: %s raised %s", type(sink).__name__, res)

    async def close(self) -> None:
        for s in self._sinks:
            try:
                await s.close()
            except Exception:
                logger.exception("FanOutSink: close failed for %s", type(s).__name__)


class CompositeSink(Sink):
    """Route each record to the most appropriate downstream sink.

    Routing rules (first match wins):
    1. payload has `entity_type` + `entity_id`     → KGSink
    2. payload has a numeric `value` (or `v`)      → TimescaleSink
    3. payload has a non-empty `text` string       → VectorSink
    4. fallback                                    → LoggingSink (no-op if not set)
    """

    def __init__(
        self,
        kg: KGSink | None = None,
        timescale: TimescaleSink | None = None,
        vector: VectorSink | None = None,
        fallback: Sink | None = None,
    ) -> None:
        self._kg = kg
        self._ts = timescale
        self._vector = vector
        self._fallback = fallback
        self.routed_kg = 0
        self.routed_ts = 0
        self.routed_vector = 0
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
        if self._vector is not None and isinstance(payload.get("text"), str) and payload["text"]:
            self.routed_vector += 1
            await self._vector.write(record)
            return
        if self._fallback is not None:
            self.routed_fallback += 1
            await self._fallback.write(record)

    def stats(self) -> dict[str, Any]:
        return {
            "kg": self.routed_kg,
            "timescale": self.routed_ts,
            "vector": self.routed_vector,
            "fallback": self.routed_fallback,
        }
