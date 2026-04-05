"""Integration tests — end-to-end flows requiring a running stack.

Run with: ``pytest tests/test_integration.py -v``
Requires: ``docker compose up``
"""

from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=60)


# ── Health & readiness ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_services_healthy(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    for service, ok in body["services"].items():
        assert ok, f"{service} is not healthy"


# ── Skills API ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_skills(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/skills")
    assert resp.status_code == 200
    body = resp.json()
    assert "skills" in body
    assert body["count"] >= 0


@pytest.mark.asyncio
async def test_list_skills_by_domain(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/skills", params={"domain": "healthcare"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_skill_not_found(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/skills/nonexistent_skill_xyz")
    assert resp.status_code == 404


# ── Agent chat ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_chat_flow(client: httpx.AsyncClient) -> None:
    async with client:
        # Start a conversation
        r1 = await client.post("/agent/chat", json={"message": "What is ContextForge?"})
        assert r1.status_code == 200
        thread_id = r1.json()["thread_id"]
        assert len(r1.json()["response"]) > 0

        # Continue the conversation
        r2 = await client.post(
            "/agent/chat",
            json={"message": "Tell me more.", "thread_id": thread_id},
        )
        assert r2.status_code == 200
        assert r2.json()["thread_id"] == thread_id


# ── Stub endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_governance_stubs(client: httpx.AsyncClient) -> None:
    async with client:
        r1 = await client.get("/governance/proposals")
        r2 = await client.get("/governance/autonomy-levels")
    assert r1.status_code == 501
    assert r2.status_code == 501


@pytest.mark.asyncio
async def test_graph_stubs(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/graph/entities")
    assert resp.status_code == 501


# ── Input validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_empty_message_rejected(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.post("/agent/chat", json={"message": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_missing_message_rejected(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.post("/agent/chat", json={})
    assert resp.status_code == 422
