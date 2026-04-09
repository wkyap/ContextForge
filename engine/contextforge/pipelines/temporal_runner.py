"""Temporal-backed runner for `DAG`s.

Lazy-imports `temporalio` so the engine still starts when the package is
absent. The DAG is translated into a workflow that calls one activity per
task in topological order, passing upstream activity results downstream.

Usage (high level):

    runner = TemporalRunner(client=temporal_client, task_queue="contextforge")
    await runner.submit(dag, workflow_id="ingest-2026-04-09")

The activities are registered dynamically on the worker; for production use
prefer pre-registered activities. This runner is intended for ad-hoc DAGs
authored by the orchestrator and the Pipeline Builder UI.
"""

from __future__ import annotations

import logging
from typing import Any

from contextforge.pipelines.dag import DAG

logger = logging.getLogger(__name__)


class TemporalNotInstalledError(RuntimeError):
    pass


class TemporalRunner:
    def __init__(self, client: Any, task_queue: str = "contextforge-pipelines") -> None:
        try:
            import temporalio  # type: ignore[import-not-found]  # noqa: F401
        except ImportError as exc:
            raise TemporalNotInstalledError(
                "temporalio is not installed. `pip install temporalio` to enable "
                "the Temporal pipeline runner."
            ) from exc
        self._client = client
        self._task_queue = task_queue

    async def submit(
        self,
        dag: DAG,
        *,
        workflow_id: str,
        run_timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Translate `dag` into activities and start a workflow.

        The dag.tasks are made available to the workflow via the global
        `_PENDING_DAGS` map keyed by workflow_id, since Temporal cannot
        serialise Python callables into workflow inputs. The worker must be
        running and have `register_pipeline_workflow()` activities loaded.
        """
        from datetime import timedelta

        from temporalio.common import RetryPolicy  # type: ignore[import-not-found]

        dag.validate()
        _PENDING_DAGS[workflow_id] = dag

        timeout = timedelta(seconds=run_timeout_s) if run_timeout_s else None
        handle = await self._client.start_workflow(
            "PipelineDAGWorkflow",
            workflow_id,
            id=workflow_id,
            task_queue=self._task_queue,
            execution_timeout=timeout,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return {"workflow_id": workflow_id, "run_id": handle.first_execution_run_id}


# Workflows can't capture closures over Python callables — the worker process
# looks tasks up by workflow id at activity time. Production deployments should
# pre-register named activities and emit a DAG of activity names instead.
_PENDING_DAGS: dict[str, DAG] = {}


def get_pending_dag(workflow_id: str) -> DAG | None:
    return _PENDING_DAGS.get(workflow_id)


def clear_pending_dag(workflow_id: str) -> None:
    _PENDING_DAGS.pop(workflow_id, None)
