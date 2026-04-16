"""Tenant context — thread-local tenant resolution for request scoping."""

from __future__ import annotations

import contextvars
from dataclasses import dataclass, field
from typing import Any

# ── Context variable ────────────────────────────────────────────────────────

_current_tenant: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "current_tenant", default=None
)

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant identity for the current request."""

    tenant_id: str
    slug: str
    name: str
    plan: str = "free"
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def kg_namespace(self) -> str:
        """Neo4j label prefix for tenant-scoped entities."""
        return f"t_{self.slug}"

    @property
    def qdrant_prefix(self) -> str:
        """Qdrant collection name prefix."""
        return f"{self.slug}_"

    @property
    def is_default(self) -> bool:
        return self.tenant_id == DEFAULT_TENANT_ID


DEFAULT_TENANT = TenantContext(
    tenant_id=DEFAULT_TENANT_ID,
    slug="default",
    name="Default Tenant",
    plan="enterprise",
)


def get_current_tenant() -> TenantContext:
    """Return the tenant for the current async context, or the default."""
    return _current_tenant.get() or DEFAULT_TENANT


def set_current_tenant(ctx: TenantContext) -> contextvars.Token[TenantContext | None]:
    """Set the tenant for the current async context. Returns a reset token."""
    return _current_tenant.set(ctx)
