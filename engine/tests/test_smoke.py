"""Smoke tests — health check + agent chat round-trip.

These tests require a running stack (``docker compose up``).
Run with: ``pytest tests/test_smoke.py -v``
"""

from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=30)


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("healthy", "degraded")
    assert "services" in body
    # At minimum Postgres and Redis should be up
    assert body["services"]["postgres"] is True
    assert body["services"]["redis"] is True


# ── Agent chat ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_agent_chat_round_trip(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.post("/agent/chat", json={"message": "Hello, who are you?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "response" in body
    assert len(body["response"]) > 0
    assert "thread_id" in body
    assert len(body["thread_id"]) > 0


@pytest.mark.asyncio
async def test_agent_chat_continues_thread(client: httpx.AsyncClient) -> None:
    async with client:
        # First message — creates a thread
        resp1 = await client.post("/agent/chat", json={"message": "Remember the number 42."})
        assert resp1.status_code == 200
        thread_id = resp1.json()["thread_id"]

        # Second message — same thread
        resp2 = await client.post(
            "/agent/chat",
            json={"message": "What number did I ask you to remember?", "thread_id": thread_id},
        )
        assert resp2.status_code == 200
        assert resp2.json()["thread_id"] == thread_id


@pytest.mark.asyncio
async def test_agent_chat_validation(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.post("/agent/chat", json={"message": ""})
    assert resp.status_code == 422  # Pydantic validation: min_length=1


# ── Stub routers return 501 ──────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/skills",
        "/graph/entities",
        "/timeseries/query",
        "/governance/proposals",
        "/onboarding/domain",
        "/pipelines",
        "/admin/audit-log",
    ],
)
async def test_stub_routers_return_501(client: httpx.AsyncClient, path: str) -> None:
    async with client:
        # Use GET for most, POST for onboarding
        method = "post" if path == "/onboarding/domain" else "get"
        resp = await getattr(client, method)(path)
    assert resp.status_code == 501
