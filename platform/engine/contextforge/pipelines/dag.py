"""DAG primitives — Task and DAG classes with cycle detection + topological sort."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


class DAGValidationError(ValueError):
    """Raised when a DAG fails validation (cycle, unknown dep, duplicate id)."""


TaskFn = Callable[..., Awaitable[Any]]


@dataclass
class Task:
    """A single node in the DAG.

    `fn` is invoked with the resolved results of its upstream tasks as keyword
    arguments (key = upstream task id) once all dependencies have completed
    successfully. Set `depends_on=[]` for root tasks.

    `activity_name` is optional and only used by the Temporal runner — it
    names a pre-registered activity on the worker. The local runner ignores
    it and always calls `fn`.
    """

    id: str
    fn: TaskFn
    depends_on: list[str] = field(default_factory=list)
    retries: int = 0
    activity_name: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise DAGValidationError("Task id must be non-empty")
        if self.retries < 0:
            raise DAGValidationError(f"Task {self.id}: retries must be >= 0")


class DAG:
    """A directed acyclic graph of async tasks.

    Tasks are added incrementally; `validate()` checks for missing
    dependencies, duplicate ids, and cycles. `topological_layers()` returns
    tasks grouped into ranks where every task in rank N can run concurrently
    once rank N-1 has completed.
    """

    def __init__(self, name: str = "dag") -> None:
        self.name = name
        self._tasks: dict[str, Task] = {}

    def add(self, task: Task) -> Task:
        if task.id in self._tasks:
            raise DAGValidationError(f"Duplicate task id: {task.id}")
        self._tasks[task.id] = task
        return task

    def task(
        self,
        id: str,
        fn: TaskFn,
        depends_on: list[str] | None = None,
        retries: int = 0,
        activity_name: str | None = None,
    ) -> Task:
        return self.add(
            Task(
                id=id,
                fn=fn,
                depends_on=list(depends_on or []),
                retries=retries,
                activity_name=activity_name,
            )
        )

    def to_spec(self) -> dict[str, Any]:
        """Serialise the DAG to a dict suitable for Temporal workflow input.

        Each task must declare an `activity_name` since plain Python callables
        cannot cross the workflow/activity boundary. The local runner does not
        use this method.
        """
        tasks = []
        for t in self._tasks.values():
            if not t.activity_name:
                raise DAGValidationError(
                    f"Task {t.id!r} needs activity_name to be Temporal-serialisable"
                )
            tasks.append(
                {
                    "id": t.id,
                    "activity": t.activity_name,
                    "depends_on": list(t.depends_on),
                    "retries": t.retries,
                }
            )
        return {"name": self.name, "tasks": tasks}

    @property
    def tasks(self) -> dict[str, Task]:
        return dict(self._tasks)

    def validate(self) -> None:
        """Raise `DAGValidationError` if the graph is malformed."""
        for t in self._tasks.values():
            for dep in t.depends_on:
                if dep not in self._tasks:
                    raise DAGValidationError(
                        f"Task {t.id!r} depends on unknown task {dep!r}"
                    )
                if dep == t.id:
                    raise DAGValidationError(f"Task {t.id!r} cannot depend on itself")
        # Cycle detection via DFS coloring (white=0, gray=1, black=2).
        color: dict[str, int] = {tid: 0 for tid in self._tasks}

        def dfs(node: str, stack: list[str]) -> None:
            color[node] = 1
            for dep in self._tasks[node].depends_on:
                if color[dep] == 1:
                    cycle = " -> ".join(stack + [node, dep])
                    raise DAGValidationError(f"Cycle detected: {cycle}")
                if color[dep] == 0:
                    dfs(dep, stack + [node])
            color[node] = 2

        for tid in self._tasks:
            if color[tid] == 0:
                dfs(tid, [])

    def topological_layers(self) -> list[list[Task]]:
        """Return tasks grouped into rank layers (Kahn-style).

        Layer 0 = tasks with no dependencies. Layer N = tasks whose deps all
        live in layers < N. Tasks within a layer have no ordering constraint
        between them and can be executed concurrently.
        """
        self.validate()
        remaining: dict[str, set[str]] = {
            tid: set(t.depends_on) for tid, t in self._tasks.items()
        }
        layers: list[list[Task]] = []
        while remaining:
            ready = [tid for tid, deps in remaining.items() if not deps]
            if not ready:  # pragma: no cover — validate() catches this
                raise DAGValidationError("Cycle remained after validation")
            layer = [self._tasks[tid] for tid in ready]
            layers.append(layer)
            for tid in ready:
                del remaining[tid]
            for deps in remaining.values():
                deps.difference_update(ready)
        return layers
