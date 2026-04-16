"""Local in-process runner for `DAG`s.

Executes tasks layer by layer with bounded concurrency. Within a layer, tasks
run in parallel via `asyncio.gather`. A task receives the results of its
upstream tasks as keyword arguments keyed by upstream task id.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from contextforge.pipelines.dag import DAG, Task

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task_id: str
    status: str  # "success" | "failed" | "skipped"
    value: Any = None
    error: str | None = None
    started_at: float = 0.0
    finished_at: float = 0.0
    attempts: int = 0


@dataclass
class RunResult:
    dag_name: str
    status: str  # "success" | "failed"
    results: dict[str, TaskResult] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0


class LocalRunner:
    """Run a `DAG` in the current process."""

    def __init__(self, max_concurrency: int = 8) -> None:
        self._sem = asyncio.Semaphore(max_concurrency)

    async def run(self, dag: DAG) -> RunResult:
        layers = dag.topological_layers()
        run = RunResult(dag_name=dag.name, status="success", started_at=time.time())
        results: dict[str, TaskResult] = run.results

        for layer in layers:
            # Skip downstream tasks whose deps already failed.
            runnable = [t for t in layer if all(
                results.get(d) and results[d].status == "success" for d in t.depends_on
            )]
            skipped = [t for t in layer if t not in runnable]
            for t in skipped:
                results[t.id] = TaskResult(
                    task_id=t.id, status="skipped",
                    error="upstream failed",
                )

            if not runnable:
                continue

            coros = [self._run_one(t, results) for t in runnable]
            done = await asyncio.gather(*coros, return_exceptions=False)
            for tr in done:
                results[tr.task_id] = tr
                if tr.status == "failed":
                    run.status = "failed"

        run.finished_at = time.time()
        return run

    async def _run_one(self, task: Task, prior: dict[str, TaskResult]) -> TaskResult:
        kwargs: dict[str, Any] = {dep: prior[dep].value for dep in task.depends_on}
        attempts = 0
        last_exc: Exception | None = None
        started = time.time()
        max_attempts = task.retries + 1
        while attempts < max_attempts:
            attempts += 1
            try:
                async with self._sem:
                    value = await task.fn(**kwargs)
                return TaskResult(
                    task_id=task.id,
                    status="success",
                    value=value,
                    started_at=started,
                    finished_at=time.time(),
                    attempts=attempts,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Task %s attempt %d/%d failed: %s",
                    task.id, attempts, max_attempts, exc,
                )
        return TaskResult(
            task_id=task.id,
            status="failed",
            error=str(last_exc) if last_exc else "unknown",
            started_at=started,
            finished_at=time.time(),
            attempts=attempts,
        )
