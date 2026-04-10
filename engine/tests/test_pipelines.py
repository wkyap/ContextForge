"""Offline tests for the pipeline DAG runner (LocalRunner)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from contextforge.pipelines import DAG, DAGValidationError, LocalRunner, Task


def test_dag_rejects_duplicate_task_ids() -> None:
    dag = DAG()
    dag.task("a", _noop)
    with pytest.raises(DAGValidationError):
        dag.task("a", _noop)


def test_dag_rejects_unknown_dependency() -> None:
    dag = DAG()
    dag.task("a", _noop, depends_on=["missing"])
    with pytest.raises(DAGValidationError):
        dag.validate()


def test_dag_rejects_self_dependency() -> None:
    dag = DAG()
    dag.task("a", _noop, depends_on=["a"])
    with pytest.raises(DAGValidationError):
        dag.validate()


def test_dag_detects_cycle() -> None:
    dag = DAG()
    dag.task("a", _noop, depends_on=["b"])
    dag.task("b", _noop, depends_on=["c"])
    dag.task("c", _noop, depends_on=["a"])
    with pytest.raises(DAGValidationError, match="Cycle"):
        dag.validate()


def test_topological_layers_groups_independent_tasks() -> None:
    dag = DAG()
    dag.task("root1", _noop)
    dag.task("root2", _noop)
    dag.task("mid", _noop, depends_on=["root1", "root2"])
    dag.task("leaf", _noop, depends_on=["mid"])
    layers = dag.topological_layers()
    assert [sorted(t.id for t in layer) for layer in layers] == [
        ["root1", "root2"],
        ["mid"],
        ["leaf"],
    ]


@pytest.mark.asyncio
async def test_local_runner_passes_upstream_results_as_kwargs() -> None:
    async def producer() -> int:
        return 7

    async def doubler(producer: int) -> int:  # noqa: ANN001
        return producer * 2

    dag = DAG("test")
    dag.task("producer", producer)
    dag.task("doubler", doubler, depends_on=["producer"])

    result = await LocalRunner().run(dag)
    assert result.status == "success"
    assert result.results["producer"].value == 7
    assert result.results["doubler"].value == 14


@pytest.mark.asyncio
async def test_local_runner_runs_layer_in_parallel() -> None:
    started: list[float] = []

    async def slow() -> None:
        started.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.1)

    dag = DAG()
    dag.task("a", slow)
    dag.task("b", slow)
    dag.task("c", slow)

    t0 = asyncio.get_event_loop().time()
    result = await LocalRunner(max_concurrency=4).run(dag)
    elapsed = asyncio.get_event_loop().time() - t0
    assert result.status == "success"
    assert elapsed < 0.25  # 3 in parallel ~= 0.1s, not 0.3s


@pytest.mark.asyncio
async def test_local_runner_skips_downstream_on_failure() -> None:
    async def boom() -> None:
        raise RuntimeError("nope")

    async def downstream(boom: Any) -> int:  # noqa: ANN001
        return 1

    dag = DAG()
    dag.task("boom", boom)
    dag.task("downstream", downstream, depends_on=["boom"])
    result = await LocalRunner().run(dag)
    assert result.status == "failed"
    assert result.results["boom"].status == "failed"
    assert result.results["downstream"].status == "skipped"


@pytest.mark.asyncio
async def test_local_runner_retries_then_succeeds() -> None:
    counter = {"n": 0}

    async def flaky() -> str:
        counter["n"] += 1
        if counter["n"] < 3:
            raise RuntimeError("flake")
        return "ok"

    dag = DAG()
    dag.task("flaky", flaky, retries=3)
    result = await LocalRunner().run(dag)
    assert result.status == "success"
    assert result.results["flaky"].attempts == 3
    assert result.results["flaky"].value == "ok"


@pytest.mark.asyncio
async def test_local_runner_retries_exhausted() -> None:
    async def always_fail() -> None:
        raise RuntimeError("nope")

    dag = DAG()
    dag.task("always", always_fail, retries=2)
    result = await LocalRunner().run(dag)
    assert result.results["always"].status == "failed"
    assert result.results["always"].attempts == 3


def test_temporal_runner_raises_clear_error_when_missing() -> None:
    # If temporalio happens to be installed in the test env, just skip.
    try:
        import temporalio  # noqa: F401
    except ImportError:
        from contextforge.pipelines.temporal_runner import (
            TemporalNotInstalledError,
            TemporalRunner,
        )

        with pytest.raises(TemporalNotInstalledError):
            TemporalRunner(client=object())


def test_dag_to_spec_requires_activity_name() -> None:
    dag = DAG()
    dag.task("a", _noop)
    with pytest.raises(DAGValidationError, match="activity_name"):
        dag.to_spec()


def test_dag_to_spec_serialises_tasks_in_temporal_shape() -> None:
    dag = DAG("ingest")
    dag.task("a", _noop, activity_name="fetch")
    dag.task("b", _noop, depends_on=["a"], retries=2, activity_name="parse")
    spec = dag.to_spec()
    assert spec["name"] == "ingest"
    by_id = {t["id"]: t for t in spec["tasks"]}
    assert by_id["a"]["activity"] == "fetch"
    assert by_id["a"]["depends_on"] == []
    assert by_id["b"]["activity"] == "parse"
    assert by_id["b"]["depends_on"] == ["a"]
    assert by_id["b"]["retries"] == 2


def test_pipeline_activity_registry_round_trip() -> None:
    from contextforge.pipelines import (
        clear_activities,
        list_activities,
        register_activity,
    )
    from contextforge.pipelines.worker import get_activity

    clear_activities()

    async def fetch() -> str:
        return "ok"

    register_activity("fetch", fetch)
    assert "fetch" in list_activities()
    assert get_activity("fetch") is fetch
    clear_activities()
    assert list_activities() == []


async def _noop(**_: Any) -> None:
    return None
