"""ASGI middleware that resolves tenant from request headers or JWT claims."""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from contextforge.tenancy.context import (
    DEFAULT_TENANT,
    TenantContext,
    set_current_tenant,
)

logger = logging.getLogger(__name__)

# Header used to override tenant in dev mode.
_TENANT_HEADER = "X-Tenant-ID"


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant identity on every request.

    Resolution order:
    1. ``X-Tenant-ID`` header (dev/testing only)
    2. ``tenant_id`` claim in JWT (when auth is enabled)
    3. Fall back to the default tenant
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant = await self._resolve(request)
        if tenant is None:
            return JSONResponse({"detail": "Unknown tenant"}, status_code=403)

        set_current_tenant(tenant)
        try:
            response = await call_next(request)
        finally:
            # Reset to avoid context leaking across requests.
            set_current_tenant(DEFAULT_TENANT)
        return response

    async def _resolve(self, request: Request) -> TenantContext | None:
        # 1. Explicit header
        header_val = request.headers.get(_TENANT_HEADER)
        if header_val:
            return await self._lookup(request, header_val)

        # 2. JWT claim (set by auth dependency)
        user: Any = request.state.__dict__.get("user")
        if user and hasattr(user, "sub"):
            # Convention: Keycloak custom claim "tenant_id"
            # When not present, fall through to default
            pass

        # 3. Default
        return DEFAULT_TENANT

    async def _lookup(self, request: Request, tenant_ref: str) -> TenantContext | None:
        """Look up tenant by ID or slug from Postgres."""
        try:
            pg = request.app.state.postgres
            row = await pg.fetch_one(
                "SELECT id, slug, name, plan, settings FROM tenants "
                "WHERE id::text = $1 OR slug = $1",
                tenant_ref,
            )
            if row is None:
                logger.warning("Tenant not found: %s", tenant_ref)
                return None
            return TenantContext(
                tenant_id=str(row["id"]),
                slug=row["slug"],
                name=row["name"],
                plan=row["plan"],
                settings=row["settings"] if isinstance(row["settings"], dict) else {},
            )
        except Exception:
            logger.warning("Tenant lookup failed for %s", tenant_ref, exc_info=True)
            return DEFAULT_TENANT
