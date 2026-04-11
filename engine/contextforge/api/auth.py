"""Keycloak JWT authentication middleware with dev-mode bypass.

When ``CONTEXTFORGE_AUTH_DISABLED=true`` (the default in development),
all requests are allowed and assigned a synthetic dev user identity.
In production, tokens are validated against the Keycloak OIDC endpoint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from contextforge.config import Settings, get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

# Cached JWKS (JSON Web Key Set) from Keycloak.
_jwks_cache: dict[str, Any] | None = None


@dataclass(frozen=True)
class UserIdentity:
    """Minimal identity extracted from the JWT."""

    sub: str  # Keycloak user ID
    email: str
    name: str
    roles: list[str]


# ── Dev bypass identity ───────────────────────────────────────────────────────

_DEV_USER = UserIdentity(
    sub="dev-user-00000000",
    email="dev@contextforge.local",
    name="Dev User",
    roles=["admin", "operator", "viewer"],
)


# ── JWKS fetcher ──────────────────────────────────────────────────────────────

async def _fetch_jwks(issuer_url: str) -> dict[str, Any]:
    global _jwks_cache  # noqa: PLW0603
    if _jwks_cache is not None:
        return _jwks_cache
    jwks_url = f"{issuer_url}/protocol/openid-connect/certs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url, timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


# ── Token validation ──────────────────────────────────────────────────────────

async def _validate_token(token: str, settings: Settings) -> UserIdentity:
    """Decode and validate a Keycloak-issued JWT.

    Uses python-jose for JWT decoding.  Falls back to a lightweight
    approach if jose is not installed (raises 501).
    """
    try:
        from jose import jwt as jose_jwt  # type: ignore[import-untyped]
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="python-jose not installed — JWT validation unavailable",
        )

    jwks = await _fetch_jwks(settings.keycloak_issuer_url)

    try:
        payload = jose_jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.keycloak_client_id,
            issuer=settings.keycloak_issuer_url,
        )
    except Exception as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Extract roles from Keycloak realm_access claim.
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])

    return UserIdentity(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        name=payload.get("name", payload.get("preferred_username", "")),
        roles=roles,
    )


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> UserIdentity:
    """Resolve the current user.  In dev mode, returns a synthetic admin."""
    if settings.auth_disabled:
        return _DEV_USER

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    return await _validate_token(credentials.credentials, settings)


# Shorthand for router dependencies.
CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]
