"""Offline unit tests for the connector stack.

These tests do NOT require Postgres/Neo4j/Qdrant/MQTT/Kafka. They cover:
- driver registry autoload
- CompositeSink routing rules
- FanOutSink failure isolation
- VectorSink batch buffering and flush
"""

from __future__ import annotations

from typing import Any

import pytest

from contextforge.connectors.base import LoggingSink, Record, Sink
from contextforge.connectors.registry import get_connector_registry
from contextforge.connectors.sinks import CompositeSink, FanOutSink, VectorSink


class CapturingSink(Sink):
    def __init__(self) -> None:
        self.records: list[Record] = []

    async def write(self, record: Record) -> None:
        self.records.append(record)


class FailingSink(Sink):
    async def write(self, record: Record) -> None:
        raise RuntimeError("boom")


class StubEmbedder:
    def __init__(self) -> None:
        self.batch_calls = 0
        self.single_calls = 0

    async def embed(self, text: str) -> list[float]:
        self.single_calls += 1
        return [float(len(text))]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return [[float(len(t))] for t in texts]


class StubQdrant:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, list[Any]]] = []

    async def upsert(self, collection: str, points: list[Any]) -> None:
        self.upserts.append((collection, points))


def test_registry_autoload_includes_all_drivers() -> None:
    kinds = get_connector_registry().list_kinds()
    for expected in ("http_poll", "kafka", "mqtt", "opcua", "sql_poll"):
        assert expected in kinds, f"missing driver: {expected}"


@pytest.mark.asyncio
async def test_composite_sink_routes_entity_to_kg() -> None:
    kg = CapturingSink()
    ts = CapturingSink()
    vec = CapturingSink()
    fb = CapturingSink()
    sink = CompositeSink(kg=kg, timescale=ts, vector=vec, fallback=fb)  # type: ignore[arg-type]

    await sink.write(Record(payload={"entity_type": "X", "entity_id": "1"}, source="t"))
    assert len(kg.records) == 1
    assert not ts.records and not vec.records and not fb.records


@pytest.mark.asyncio
async def test_composite_sink_routes_numeric_to_timescale() -> None:
    kg = CapturingSink()
    ts = CapturingSink()
    vec = CapturingSink()
    sink = CompositeSink(kg=kg, timescale=ts, vector=vec)  # type: ignore[arg-type]

    await sink.write(Record(payload={"value": 3.14}, source="t"))
    assert len(ts.records) == 1 and not vec.records


@pytest.mark.asyncio
async def test_composite_sink_routes_text_to_vector() -> None:
    kg = CapturingSink()
    ts = CapturingSink()
    vec = CapturingSink()
    fb = CapturingSink()
    sink = CompositeSink(kg=kg, timescale=ts, vector=vec, fallback=fb)  # type: ignore[arg-type]

    await sink.write(Record(payload={"text": "hello world"}, source="t"))
    assert len(vec.records) == 1 and not fb.records


@pytest.mark.asyncio
async def test_composite_sink_falls_back_for_unknown_shape() -> None:
    fb = CapturingSink()
    sink = CompositeSink(fallback=fb)
    await sink.write(Record(payload={"unknown": True}, source="t"))
    assert len(fb.records) == 1


@pytest.mark.asyncio
async def test_fanout_sink_isolates_failures() -> None:
    good = CapturingSink()
    bad = FailingSink()
    sink = FanOutSink([good, bad])
    # Should not raise even though `bad` throws.
    await sink.write(Record(payload={"x": 1}, source="t"))
    assert len(good.records) == 1


@pytest.mark.asyncio
async def test_vector_sink_batch_flushes_when_full() -> None:
    embedder = StubEmbedder()
    qdrant = StubQdrant()
    sink = VectorSink(qdrant=qdrant, embedder=embedder, batch_size=3)  # type: ignore[arg-type]

    for i in range(3):
        await sink.write(Record(payload={"text": f"doc {i}"}, source="t"))

    assert embedder.batch_calls == 1
    assert embedder.single_calls == 0
    assert len(qdrant.upserts) == 1
    _, points = qdrant.upserts[0]
    assert len(points) == 3
    assert sink.written == 3


@pytest.mark.asyncio
async def test_vector_sink_close_flushes_partial_batch() -> None:
    embedder = StubEmbedder()
    qdrant = StubQdrant()
    sink = VectorSink(qdrant=qdrant, embedder=embedder, batch_size=10)  # type: ignore[arg-type]

    await sink.write(Record(payload={"text": "only one"}, source="t"))
    assert qdrant.upserts == []  # buffered
    await sink.close()
    assert len(qdrant.upserts) == 1
    assert sink.written == 1


@pytest.mark.asyncio
async def test_vector_sink_single_mode_uses_per_record_path() -> None:
    embedder = StubEmbedder()
    qdrant = StubQdrant()
    sink = VectorSink(qdrant=qdrant, embedder=embedder, batch_size=1)  # type: ignore[arg-type]

    await sink.write(Record(payload={"text": "x"}, source="t"))
    assert embedder.single_calls == 1
    assert embedder.batch_calls == 0
    assert sink.written == 1


@pytest.mark.asyncio
async def test_vector_sink_skips_non_text_records() -> None:
    embedder = StubEmbedder()
    qdrant = StubQdrant()
    sink = VectorSink(qdrant=qdrant, embedder=embedder, batch_size=2)  # type: ignore[arg-type]

    await sink.write(Record(payload={"value": 5}, source="t"))
    assert sink.skipped == 1
    assert sink.written == 0


@pytest.mark.asyncio
async def test_logging_sink_counts_records() -> None:
    sink = LoggingSink()
    await sink.write(Record(payload={"x": 1}, source="t"))
    await sink.write(Record(payload={"x": 2}, source="t"))
    assert sink.count == 2
