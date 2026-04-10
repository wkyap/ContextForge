"""Temporal worker for the pipeline DAG runner.

Defines:
- `execute_pipeline_task` — generic activity that looks a callable up by
  name in a process-local registry and invokes it with the upstream task
  results passed in as kwargs.
- `PipelineDAGWorkflow` — workflow that consumes a `DAG.to_spec()` dict
  and orchestrates one activity per task in dependency order.
- `register_activity(name, fn)` and `run_worker(client, task_queue)` —
  ergonomic helpers for booting a worker process.

Lazy-imports `temporalio` so callers without it installed can still import
this module's helpers without crash; only `run_worker()` and the workflow
class actually require the dependency.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

ActivityFn = Callable[..., Awaitable[Any]]

# Process-local registry of named activities. Workers populate this before
# `run_worker()` so the generic activity can dispatch by name.
_ACTIVITIES: dict[str, ActivityFn] = {}


def register_activity(name: str, fn: ActivityFn) -> None:
    if name in _ACTIVITIES:
        logger.warning("Replacing existing pipeline activity %r", name)
    _ACTIVITIES[name] = fn


def get_activity(name: str) -> ActivityFn | None:
    return _ACTIVITIES.get(name)


def list_activities() -> list[str]:
    return sorted(_ACTIVITIES)


def clear_activities() -> None:
    _ACTIVITIES.clear()


def _build_workflow_class() -> type:
    """Construct the workflow class only when temporalio is importable."""
    from datetime import timedelta

    from temporalio import workflow  # type: ignore[import-not-found]

    @workflow.defn(name="PipelineDAGWorkflow")
    class PipelineDAGWorkflow:
        @workflow.run
        async def run(self, spec: dict[str, Any]) -> dict[str, Any]:
            tasks: list[dict[str, Any]] = list(spec.get("tasks", []))
            results: dict[str, Any] = {}
            failed: dict[str, str] = {}
            skipped: set[str] = set()

            # Resolve in topological waves; within a wave, await sequentially
            # for determinism (Temporal workflows must be deterministic and
            # asyncio.gather of activities is supported but adds complexity).
            done: set[str] = set()
            remaining = list(tasks)
            while remaining:
                ready = [
                    t for t in remaining
                    if all(d in done for d in t["depends_on"])
                ]
                if not ready:
                    workflow.logger.error(
                        "PipelineDAGWorkflow: no runnable tasks (cycle?)"
                    )
                    break
                for t in ready:
                    remaining.remove(t)
                    upstream_failed = [
                        d for d in t["depends_on"] if d in failed or d in skipped
                    ]
                    if upstream_failed:
                        skipped.add(t["id"])
                        done.add(t["id"])
                        continue
                    kwargs = {d: results[d] for d in t["depends_on"]}
                    try:
                        value = await workflow.execute_activity(
                            "execute_pipeline_task",
                            args=[t["activity"], kwargs],
                            start_to_close_timeout=timedelta(minutes=10),
                        )
                        results[t["id"]] = value
                    except Exception as exc:  # noqa: BLE001
                        failed[t["id"]] = str(exc)
                        workflow.logger.warning(
                            "Task %s failed: %s", t["id"], exc
                        )
                    done.add(t["id"])

            return {
                "name": spec.get("name"),
                "results": results,
                "failed": failed,
                "skipped": sorted(skipped),
                "status": "failed" if failed or skipped else "success",
            }

    return PipelineDAGWorkflow


def _build_activity() -> ActivityFn:
    from temporalio import activity  # type: ignore[import-not-found]

    @activity.defn(name="execute_pipeline_task")
    async def execute_pipeline_task(activity_name: str, kwargs: dict[str, Any]) -> Any:
        fn = _ACTIVITIES.get(activity_name)
        if fn is None:
            raise LookupError(
                f"No pipeline activity registered with name {activity_name!r}. "
                f"Known: {list_activities()}"
            )
        return await fn(**kwargs)

    return execute_pipeline_task


async def run_worker(
    client: Any,
    task_queue: str = "contextforge-pipelines",
) -> None:
    """Boot a Temporal worker that handles `PipelineDAGWorkflow`.

    Activities must be registered via `register_activity()` BEFORE this is
    called. The worker runs until cancelled.
    """
    try:
        from temporalio.worker import Worker  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "temporalio is not installed. `pip install temporalio` to run a worker."
        ) from exc

    workflow_cls = _build_workflow_class()
    activity_fn = _build_activity()
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[workflow_cls],
        activities=[activity_fn],
    )
    logger.info(
        "Pipeline DAG worker starting on task_queue=%s with %d activity(ies): %s",
        task_queue, len(_ACTIVITIES), list_activities(),
    )
    await worker.run()
