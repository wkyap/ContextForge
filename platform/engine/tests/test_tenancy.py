"""Tests for multi-tenant scoping and budget controller."""

from __future__ import annotations

import base64
import json

from contextforge.tenancy.budget import BudgetStatus
from contextforge.tenancy.context import (
    DEFAULT_TENANT,
    DEFAULT_TENANT_ID,
    TenantContext,
    get_current_tenant,
    set_current_tenant,
)
from contextforge.tenancy.middleware import _decode_jwt_payload

# ── TenantContext ────────────────────────────────────────────────────────────

def test_default_tenant_exists() -> None:
    assert DEFAULT_TENANT.tenant_id == DEFAULT_TENANT_ID
    assert DEFAULT_TENANT.slug == "default"
    assert DEFAULT_TENANT.is_default is True


def test_tenant_context_properties() -> None:
    ctx = TenantContext(
        tenant_id="abc-123",
        slug="acme",
        name="Acme Corp",
        plan="pro",
    )
    assert ctx.kg_namespace == "t_acme"
    assert ctx.qdrant_prefix == "acme_"
    assert ctx.is_default is False


def test_context_var_default() -> None:
    assert get_current_tenant() is DEFAULT_TENANT


def test_context_var_set_and_reset() -> None:
    custom = TenantContext(tenant_id="t1", slug="test", name="Test", plan="starter")
    set_current_tenant(custom)
    assert get_current_tenant() is custom

    # Reset
    set_current_tenant(DEFAULT_TENANT)
    assert get_current_tenant() is DEFAULT_TENANT


# ── BudgetStatus ─────────────────────────────────────────────────────────────

def test_budget_within_limits() -> None:
    status = BudgetStatus(
        tenant_id="t1",
        period="monthly",
        max_tokens=1_000_000,
        max_cost_usd=50.0,
        max_requests=10_000,
        tokens_used=500_000,
        cost_used_usd=25.0,
        requests_used=5_000,
    )
    assert status.tokens_remaining == 500_000
    assert status.cost_remaining_usd == 25.0
    assert status.requests_remaining == 5_000
    assert status.over_budget is False


def test_budget_over_tokens() -> None:
    status = BudgetStatus(
        tenant_id="t1",
        period="monthly",
        max_tokens=1_000_000,
        max_cost_usd=50.0,
        max_requests=10_000,
        tokens_used=1_000_001,
        cost_used_usd=0.0,
        requests_used=0,
    )
    assert status.over_budget is True
    assert status.tokens_remaining == 0


def test_budget_over_cost() -> None:
    status = BudgetStatus(
        tenant_id="t1",
        period="monthly",
        max_tokens=1_000_000,
        max_cost_usd=50.0,
        max_requests=10_000,
        tokens_used=0,
        cost_used_usd=50.01,
        requests_used=0,
    )
    assert status.over_budget is True


def test_budget_over_requests() -> None:
    status = BudgetStatus(
        tenant_id="t1",
        period="monthly",
        max_tokens=1_000_000,
        max_cost_usd=50.0,
        max_requests=10_000,
        tokens_used=0,
        cost_used_usd=0.0,
        requests_used=10_001,
    )
    assert status.over_budget is True


def test_budget_to_dict() -> None:
    status = BudgetStatus(
        tenant_id="t1",
        period="monthly",
        max_tokens=100,
        max_cost_usd=10.0,
        max_requests=50,
        tokens_used=30,
        cost_used_usd=3.0,
        requests_used=10,
    )
    d = status.to_dict()
    assert d["tokens"]["remaining"] == 70
    assert d["cost_usd"]["remaining"] == 7.0
    assert d["requests"]["remaining"] == 40
    assert d["over_budget"] is False


# ── JWT payload decoder ──────────────────────────────────────────────────────


def _make_jwt(payload: dict[str, object]) -> str:
    """Build a fake unsigned JWT for testing the payload decoder."""
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = _b64(b'{"alg":"none","typ":"JWT"}')
    body = _b64(json.dumps(payload).encode())
    return f"{header}.{body}.signature"


def test_jwt_decode_extracts_tenant_claim() -> None:
    token = _make_jwt({"sub": "user-1", "tenant_id": "acme", "email": "u@a.io"})
    decoded = _decode_jwt_payload(token)
    assert decoded is not None
    assert decoded["tenant_id"] == "acme"
    assert decoded["sub"] == "user-1"


def test_jwt_decode_handles_missing_claim() -> None:
    token = _make_jwt({"sub": "user-1"})
    decoded = _decode_jwt_payload(token)
    assert decoded is not None
    assert "tenant_id" not in decoded


def test_jwt_decode_rejects_malformed_token() -> None:
    assert _decode_jwt_payload("not.a.jwt.at.all") is None
    assert _decode_jwt_payload("oneonly") is None
    assert _decode_jwt_payload("a.b") is None
    assert _decode_jwt_payload("a.!!!notbase64!!!.c") is None


def test_jwt_decode_handles_padding_variations() -> None:
    # Payloads of different lengths exercise the base64 padding logic.
    for sub in ("a", "ab", "abc", "abcd"):
        token = _make_jwt({"sub": sub, "tenant_id": "t1"})
        decoded = _decode_jwt_payload(token)
        assert decoded is not None
        assert decoded["sub"] == sub
        assert decoded["tenant_id"] == "t1"
