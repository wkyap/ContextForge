"""Shared dependencies injected into every PydanticAI agent at runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentDeps:
    """Dependencies available to all PydanticAI agents via ``ctx.deps``.

    Constructed fresh for each LangGraph node invocation from the current
    ``AgentState`` and application configuration.
    """

    domain: str = "industrial"
    db_uri: str = ""
    skill_catalog: dict[str, Any] = field(default_factory=dict)
    budget_remaining_usd: float = 1.0
    user_id: str = "anonymous"
