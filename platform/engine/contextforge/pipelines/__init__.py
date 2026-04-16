"""Pipeline DAG runner — declarative async task graphs.

Provides a small, dependency-aware runner that executes async callables in
topological order with bounded concurrency. The same `DAG` can be executed
in-process by `LocalRunner` or submitted to a Temporal worker via
`TemporalRunner` (lazy import).
"""

from contextforge.pipelines.dag import DAG, DAGValidationError, Task
from contextforge.pipelines.runner import LocalRunner, TaskResult
from contextforge.pipelines.worker import (
    clear_activities,
    list_activities,
    register_activity,
)

__all__ = [
    "DAG",
    "DAGValidationError",
    "LocalRunner",
    "Task",
    "TaskResult",
    "clear_activities",
    "list_activities",
    "register_activity",
]
