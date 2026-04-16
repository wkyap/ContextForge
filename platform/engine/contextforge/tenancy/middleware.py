"""ASGI middleware that resolves tenant from request headers or JWT claims."""

from __future__ import annotations

import base64
import binascii
import json
import logging

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
# Convention: Keycloak custom claim that carries the tenant id/slug.
_JWT_TENANT_CLAIM = "tenant_id"


def _decode_jwt_payload(token: str) -> dict[str, object] | None:
    """Decode a JWT payload **without verifying the signature**.

    Tenant resolution is a routing concern — signature validation still
    happens in ``api/auth.get_current_user`` before the request reaches
    business logic. We just need the ``tenant_id`` claim early enough to
    set the context for downstream code.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Add padding for base64 decoding (JWT uses base64url without padding).
        padding = "=" * (-len(payload_b64) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else None
    except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant identity on every request.

    Resolution order:
    1. ``X-Tenant-ID`` header (dev/testing only)
    2. ``tenant_id`` claim in the JWT carried in the ``Authorization`` header
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
        # 1. Explicit header (dev/testing override)
        header_val = request.headers.get(_TENANT_HEADER)
        if header_val:
            return await self._lookup(request, header_val)

        # 2. tenant_id claim from the bearer JWT
        tenant_ref = self._tenant_from_authorization(request)
        if tenant_ref:
            looked_up = await self._lookup(request, tenant_ref)
            if looked_up is not None:
                return looked_up
            # Token referenced an unknown tenant — reject hard.
            return None

        # 3. Default
        return DEFAULT_TENANT

    @staticmethod
    def _tenant_from_authorization(request: Request) -> str | None:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        payload = _decode_jwt_payload(token)
        if not payload:
            return None
        claim = payload.get(_JWT_TENANT_CLAIM)
        if isinstance(claim, str) and claim:
            return claim
        return None

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
