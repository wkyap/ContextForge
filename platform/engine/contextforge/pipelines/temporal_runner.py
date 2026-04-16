"""Temporal-backed runner for `DAG`s — submission side.

Lazy-imports `temporalio` so the engine still starts when the package is
absent. The DAG is serialised via `DAG.to_spec()` (each task must declare
`activity_name`) and shipped as the workflow input. The worker module
(`worker.py`) defines the workflow + activity that consume that spec.
"""

from __future__ import annotations

import logging
from typing import Any

from contextforge.pipelines.dag import DAG

logger = logging.getLogger(__name__)


class TemporalNotInstalledError(RuntimeError):
    pass


class TemporalRunner:
    """Submit a `DAG` to a Temporal cluster.

    The caller is responsible for running a worker (see
    `contextforge.pipelines.worker.run_worker`) registered with the activity
    callables that the DAG references by name.
    """

    def __init__(self, client: Any, task_queue: str = "contextforge-pipelines") -> None:
        try:
            import temporalio  # noqa: F401
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
        from datetime import timedelta

        from temporalio.common import RetryPolicy

        spec = dag.to_spec()  # raises if any task lacks activity_name
        timeout = timedelta(seconds=run_timeout_s) if run_timeout_s else None
        handle = await self._client.start_workflow(
            "PipelineDAGWorkflow",
            spec,
            id=workflow_id,
            task_queue=self._task_queue,
            execution_timeout=timeout,
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return {"workflow_id": workflow_id, "run_id": handle.first_execution_run_id}
