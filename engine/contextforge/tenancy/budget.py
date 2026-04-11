"""Per-tenant budget enforcement — token/cost/request limits."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BudgetStatus:
    """Snapshot of a tenant's budget state."""

    tenant_id: str
    period: str
    max_tokens: int
    max_cost_usd: float
    max_requests: int
    tokens_used: int
    cost_used_usd: float
    requests_used: int

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.max_tokens - self.tokens_used)

    @property
    def cost_remaining_usd(self) -> float:
        return max(0.0, self.max_cost_usd - self.cost_used_usd)

    @property
    def requests_remaining(self) -> int:
        return max(0, self.max_requests - self.requests_used)

    @property
    def over_budget(self) -> bool:
        return (
            self.tokens_used >= self.max_tokens
            or self.cost_used_usd >= self.max_cost_usd
            or self.requests_used >= self.max_requests
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "period": self.period,
            "tokens": {
                "used": self.tokens_used,
                "max": self.max_tokens,
                "remaining": self.tokens_remaining,
            },
            "cost_usd": {
                "used": float(self.cost_used_usd),
                "max": float(self.max_cost_usd),
                "remaining": self.cost_remaining_usd,
            },
            "requests": {
                "used": self.requests_used,
                "max": self.max_requests,
                "remaining": self.requests_remaining,
            },
            "over_budget": self.over_budget,
        }


class TenantBudgetController:
    """Enforce and track per-tenant usage budgets.

    Reads/writes the ``tenant_budgets`` and ``tenant_usage_log`` tables.
    Designed to be called from the agent graph ``budget_check`` node and
    from API middleware.
    """

    def __init__(self, postgres: Any) -> None:
        self._pg = postgres

    async def get_budget(self, tenant_id: str, period: str = "monthly") -> BudgetStatus | None:
        """Get current budget status for a tenant."""
        row = await self._pg.fetch_one(
            """SELECT max_tokens, max_cost_usd, max_requests,
                      tokens_used, cost_used_usd, requests_used, period
               FROM tenant_budgets
               WHERE tenant_id = $1::uuid AND period = $2""",
            tenant_id, period,
        )
        if row is None:
            return None
        return BudgetStatus(
            tenant_id=tenant_id,
            period=row["period"],
            max_tokens=row["max_tokens"],
            max_cost_usd=float(row["max_cost_usd"]),
            max_requests=row["max_requests"],
            tokens_used=row["tokens_used"],
            cost_used_usd=float(row["cost_used_usd"]),
            requests_used=row["requests_used"],
        )

    async def check_budget(self, tenant_id: str) -> bool:
        """Return True if tenant is within budget, False if over."""
        status = await self.get_budget(tenant_id)
        if status is None:
            # No budget configured — allow by default
            return True
        return not status.over_budget

    async def record_usage(
        self,
        tenant_id: str,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        user_id: str = "",
        operation: str = "agent_chat",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record usage and increment budget counters atomically."""
        # Log the individual usage event
        import json

        await self._pg.execute(
            """INSERT INTO tenant_usage_log
               (tenant_id, user_id, operation, tokens_used, cost_usd, metadata)
               VALUES ($1::uuid, $2, $3, $4, $5, $6)""",
            [tenant_id, user_id, operation, tokens, cost_usd,
             json.dumps(metadata or {})],
        )

        # Increment the budget counters
        await self._pg.execute(
            """UPDATE tenant_budgets
               SET tokens_used = tokens_used + $2,
                   cost_used_usd = cost_used_usd + $3,
                   requests_used = requests_used + 1,
                   updated_at = now()
               WHERE tenant_id = $1::uuid AND period = 'monthly'""",
            [tenant_id, tokens, cost_usd],
        )

    async def reset_period(self, tenant_id: str, period: str = "monthly") -> None:
        """Reset usage counters for a new billing period."""
        await self._pg.execute(
            """UPDATE tenant_budgets
               SET tokens_used = 0, cost_used_usd = 0, requests_used = 0,
                   period_start = now(), updated_at = now()
               WHERE tenant_id = $1::uuid AND period = $2""",
            [tenant_id, period],
        )
        logger.info("Reset %s budget for tenant %s", period, tenant_id)

    async def update_limits(
        self,
        tenant_id: str,
        *,
        max_tokens: int | None = None,
        max_cost_usd: float | None = None,
        max_requests: int | None = None,
    ) -> None:
        """Update budget limits for a tenant."""
        updates: list[str] = []
        params: list[Any] = []
        idx = 1

        if max_tokens is not None:
            updates.append(f"max_tokens = ${idx}")
            params.append(max_tokens)
            idx += 1
        if max_cost_usd is not None:
            updates.append(f"max_cost_usd = ${idx}")
            params.append(max_cost_usd)
            idx += 1
        if max_requests is not None:
            updates.append(f"max_requests = ${idx}")
            params.append(max_requests)
            idx += 1

        if not updates:
            return

        updates.append("updated_at = now()")
        params.append(tenant_id)
        await self._pg.execute(
            f"UPDATE tenant_budgets SET {', '.join(updates)} "
            f"WHERE tenant_id = ${idx}::uuid AND period = 'monthly'",
            params,
        )
