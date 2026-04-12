"""Offline unit tests for the connector stack.

These tests do NOT require Postgres/Neo4j/Qdrant/MQTT/Kafka. They cover:
- driver registry autoload
- CompositeSink routing rules
- FanOutSink failure isolation
- VectorSink batch buffering and flush
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from contextforge.connectors.base import ConnectorBase, LoggingSink, Record, Sink
from contextforge.connectors.dlq import DLQRepository
from contextforge.connectors.registry import get_connector_registry
from contextforge.connectors.runtime import ConnectorSupervisor
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


class FakeConnector(ConnectorBase):
    source_kind = "fake"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self.connect_called = False
        self.close_called = False

    async def connect(self) -> None:
        self.connect_called = True
        if self.config.get("fail_connect"):
            raise RuntimeError("nope")

    async def stream(self) -> AsyncIterator[Record]:
        n = int(self.config.get("emit", 3))
        for i in range(n):
            yield Record(payload={"i": i, **self.config.get("payload", {})}, source=f"fake://{self.name}")
            await asyncio.sleep(0)
        # Then idle until cancelled
        while True:
            await asyncio.sleep(0.01)

    async def close(self) -> None:
        self.close_called = True


# Register once for the supervisor tests.
get_connector_registry().register(FakeConnector)


class FakeSkill:
    def __init__(self, name: str, metadata: dict[str, Any]) -> None:
        self.name = name
        self.metadata = metadata


class FakeSkillRegistry:
    def __init__(self, skills: list[FakeSkill]) -> None:
        self._skills = skills

    def list_by_type(self, type_: str) -> list[FakeSkill]:
        return list(self._skills)


class FakeConfig:
    def __init__(self, name: str, source_kind: str, config: dict[str, Any], sink: str | None = None) -> None:
        self.name = name
        self.source_kind = source_kind
        self.config = config
        self.sink = sink


class FakeRepo:
    def __init__(self, configs: list[FakeConfig]) -> None:
        self._configs = configs

    async def list_all(self, enabled_only: bool = False) -> list[FakeConfig]:
        return list(self._configs)


@pytest.mark.asyncio
async def test_supervisor_start_streams_to_default_sink() -> None:
    capture = CapturingSink()
    sup = ConnectorSupervisor(sink=capture)
    await sup.start("c1", "fake", {"emit": 3})
    # Wait for emission to flush.
    for _ in range(50):
        if len(capture.records) >= 3:
            break
        await asyncio.sleep(0.01)
    assert len(capture.records) == 3
    assert sup.get("c1") is not None
    await sup.stop("c1")
    assert sup.get("c1") is None


@pytest.mark.asyncio
async def test_supervisor_per_connector_sink_override() -> None:
    default = CapturingSink()
    alt = CapturingSink()
    sup = ConnectorSupervisor(sink=default)
    sup.register_sink("alt", alt)
    assert "alt" in sup.list_sinks()
    await sup.start("c1", "fake", {"emit": 2}, sink_name="alt")
    for _ in range(50):
        if len(alt.records) >= 2:
            break
        await asyncio.sleep(0.01)
    assert len(alt.records) == 2
    assert default.records == []
    await sup.shutdown()


@pytest.mark.asyncio
async def test_supervisor_unknown_sink_raises() -> None:
    sup = ConnectorSupervisor(sink=CapturingSink())
    with pytest.raises(KeyError):
        await sup.start("c1", "fake", {}, sink_name="missing")


@pytest.mark.asyncio
async def test_supervisor_duplicate_name_raises() -> None:
    sup = ConnectorSupervisor(sink=CapturingSink())
    await sup.start("c1", "fake", {"emit": 1})
    with pytest.raises(ValueError):
        await sup.start("c1", "fake", {"emit": 1})
    await sup.shutdown()


@pytest.mark.asyncio
async def test_supervisor_failed_connect_propagates() -> None:
    sup = ConnectorSupervisor(sink=CapturingSink())
    with pytest.raises(RuntimeError):
        await sup.start("c1", "fake", {"fail_connect": True})
    assert sup.get("c1") is None


@pytest.mark.asyncio
async def test_autostart_from_registry_starts_only_flagged() -> None:
    skills = [
        FakeSkill("on", {"source_kind": "fake", "autostart": True, "config": {"emit": 1}}),
        FakeSkill("off", {"source_kind": "fake", "autostart": False, "config": {"emit": 1}}),
        FakeSkill("nokind", {"autostart": True}),
    ]
    sup = ConnectorSupervisor(sink=CapturingSink())
    started = await sup.autostart_from_registry(FakeSkillRegistry(skills))
    assert started == 1
    assert sup.get("on") is not None
    assert sup.get("off") is None
    await sup.shutdown()


@pytest.mark.asyncio
async def test_autostart_from_db_starts_all_rows() -> None:
    repo = FakeRepo([
        FakeConfig("a", "fake", {"emit": 1}),
        FakeConfig("b", "fake", {"emit": 1}),
    ])
    sup = ConnectorSupervisor(sink=CapturingSink())
    started = await sup.autostart_from_db(repo)
    assert started == 2
    await sup.shutdown()


@pytest.mark.asyncio
async def test_supervisor_shutdown_closes_connectors() -> None:
    sup = ConnectorSupervisor(sink=CapturingSink())
    conn = await sup.start("c1", "fake", {"emit": 1})
    await sup.shutdown()
    assert isinstance(conn, FakeConnector)
    assert conn.close_called is True


@pytest.mark.asyncio
async def test_logging_sink_counts_records() -> None:
    sink = LoggingSink()
    await sink.write(Record(payload={"x": 1}, source="t"))
    await sink.write(Record(payload={"x": 2}, source="t"))
    assert sink.count == 2


# ── Dead-letter queue ────────────────────────────────────────────────────────


class StubDLQ:
    """Captures DLQ writes without hitting Postgres."""

    def __init__(self) -> None:
        self.writes: list[dict[str, Any]] = []

    async def write(
        self,
        *,
        connector_name: str,
        record: Record,
        error: str,
        sink_name: str | None = None,
    ) -> None:
        self.writes.append({
            "connector_name": connector_name,
            "sink_name": sink_name,
            "source": record.source,
            "payload": record.payload,
            "error": error,
        })


@pytest.mark.asyncio
async def test_supervisor_routes_sink_failures_to_dlq() -> None:
    """A sink that raises should land its record in the DLQ."""
    dlq = StubDLQ()
    sup = ConnectorSupervisor(sink=FailingSink(), dlq=dlq)  # type: ignore[arg-type]
    await sup.start("crashy", "fake", {"emit": 2})
    for _ in range(50):
        if len(dlq.writes) >= 2:
            break
        await asyncio.sleep(0.01)
    await sup.shutdown()
    assert len(dlq.writes) == 2
    assert all(w["connector_name"] == "crashy" for w in dlq.writes)
    assert all("boom" in w["error"] for w in dlq.writes)


@pytest.mark.asyncio
async def test_supervisor_dlq_records_named_sink_override() -> None:
    """DLQ rows should know which named sink originally rejected the record."""
    dlq = StubDLQ()
    sup = ConnectorSupervisor(sink=CapturingSink(), dlq=dlq)  # type: ignore[arg-type]
    sup.register_sink("badalt", FailingSink())
    await sup.start("c1", "fake", {"emit": 1}, sink_name="badalt")
    for _ in range(50):
        if dlq.writes:
            break
        await asyncio.sleep(0.01)
    await sup.shutdown()
    assert dlq.writes
    assert dlq.writes[0]["sink_name"] == "badalt"


@pytest.mark.asyncio
async def test_supervisor_without_dlq_does_not_crash_on_sink_failure() -> None:
    """Supervisor should keep streaming even when no DLQ is configured."""
    sup = ConnectorSupervisor(sink=FailingSink())  # type: ignore[arg-type]
    await sup.start("c1", "fake", {"emit": 3})
    # Give it time — no records should be captured but the loop must not crash.
    await asyncio.sleep(0.05)
    assert sup.get("c1") is not None
    await sup.shutdown()


class FakePostgres:
    """In-memory stand-in for the Postgres client used by DLQRepository."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.fail_writes = False

    async def execute(self, sql: str, params: list[Any] | None = None) -> None:
        if self.fail_writes:
            raise RuntimeError("postgres down")
        self.executed.append((sql, params or []))


@pytest.mark.asyncio
async def test_dlq_repository_write_persists_record() -> None:
    pg = FakePostgres()
    repo = DLQRepository(pg)
    rec = Record(
        payload={"id": 1, "value": 99},
        source="fake://x",
        timestamp=1234.5,
        metadata={"k": "v"},
    )
    await repo.write(
        connector_name="my-connector",
        record=rec,
        error="boom",
        sink_name="kg",
    )
    assert len(pg.executed) == 1
    sql, params = pg.executed[0]
    assert "INSERT INTO connector_dlq" in sql
    assert params[0] == "my-connector"
    assert params[1] == "kg"
    assert params[2] == "fake://x"
    assert params[5] == "boom"
    assert params[6] == 1234.5


@pytest.mark.asyncio
async def test_dlq_repository_write_swallows_postgres_failure() -> None:
    """DLQ writes must never crash the ingestion loop."""
    pg = FakePostgres()
    pg.fail_writes = True
    repo = DLQRepository(pg)
    # Should NOT raise.
    await repo.write(
        connector_name="x",
        record=Record(payload={}, source="t"),
        error="e",
    )
