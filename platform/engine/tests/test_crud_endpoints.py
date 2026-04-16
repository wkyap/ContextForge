"""Integration tests for tenant, agent_config, and quality CRUD endpoints.

These tests use a mock PostgresClient so they run offline (no DB required).
They exercise the HTTP layer: routing, validation, serialization, and
the interaction between routes and the DB client.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from contextforge.api.deps import _get_postgres
from contextforge.api.v1 import agent_configs, quality, tenants
from contextforge.db.postgres import PostgresClient

# ── Fixtures ──────────────────────────────────────────────────────────────────


class FakeRecord(dict[str, Any]):
    """dict subclass that also supports attribute access like asyncpg.Record."""

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(key)


def _records(rows: list[dict[str, Any]]) -> list[FakeRecord]:
    return [FakeRecord(r) for r in rows]


@pytest.fixture()
def mock_pg() -> AsyncMock:
    pg = AsyncMock(spec=PostgresClient)
    pg.execute.return_value = "INSERT 0 1"
    pg.fetch.return_value = []
    pg.fetch_one.return_value = None
    pg.fetchrow.return_value = None
    pg.fetchval.return_value = 0
    return pg


@pytest.fixture()
def app(mock_pg: AsyncMock) -> FastAPI:
    test_app = FastAPI()
    prefix = "/api/v1"
    test_app.include_router(tenants.router, prefix=prefix)
    test_app.include_router(agent_configs.router, prefix=prefix)
    test_app.include_router(quality.router, prefix=prefix)

    test_app.dependency_overrides[_get_postgres] = lambda: mock_pg
    return test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test",
    ) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════════
# Tenant CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestTenantList:
    async def test_list_tenants_empty(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get("/api/v1/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["tenants"] == []

    async def test_list_tenants_with_data(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        tid = str(uuid.uuid4())
        mock_pg.fetch.return_value = _records([
            {"id": tid, "slug": "acme", "name": "Acme", "plan": "pro"},
        ])
        mock_pg.fetchval.return_value = 1
        resp = await client.get("/api/v1/tenants")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["tenants"][0]["slug"] == "acme"


class TestTenantCreate:
    async def test_create_tenant_success(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        resp = await client.post(
            "/api/v1/tenants",
            json={"slug": "acme", "name": "Acme Corp", "plan": "pro"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["slug"] == "acme"
        assert "id" in body
        # Should have called execute twice: INSERT tenant + INSERT budget
        assert mock_pg.execute.call_count == 2

    async def test_create_tenant_default_plan(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        resp = await client.post(
            "/api/v1/tenants",
            json={"slug": "beta", "name": "Beta Inc"},
        )
        assert resp.status_code == 201
        assert mock_pg.execute.call_count == 2

    async def test_create_tenant_invalid_slug(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/tenants",
            json={"slug": "INVALID SLUG!", "name": "Bad"},
        )
        assert resp.status_code == 422

    async def test_create_tenant_invalid_plan(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/tenants",
            json={"slug": "ok", "name": "OK", "plan": "mega"},
        )
        assert resp.status_code == 422

    async def test_create_tenant_missing_name(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/tenants", json={"slug": "ok"},
        )
        assert resp.status_code == 422


class TestTenantBudget:
    async def test_get_budget_tenant_not_found(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch_one.return_value = None
        resp = await client.get("/api/v1/tenants/nonexistent/budget")
        assert resp.status_code == 404

    async def test_update_budget_tenant_not_found(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch_one.return_value = None
        resp = await client.put(
            "/api/v1/tenants/nonexistent/budget",
            json={"max_tokens": 500_000},
        )
        assert resp.status_code == 404


class TestTenantUsage:
    async def test_get_usage_tenant_not_found(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch_one.return_value = None
        resp = await client.get("/api/v1/tenants/nonexistent/usage")
        assert resp.status_code == 404

    async def test_get_usage_empty(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        tid = str(uuid.uuid4())
        mock_pg.fetch_one.return_value = FakeRecord({"id": tid})
        mock_pg.fetch.return_value = []
        resp = await client.get(f"/api/v1/tenants/{tid}/usage")
        assert resp.status_code == 200
        body = resp.json()
        assert body["tenant_id"] == tid
        assert body["usage"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Config CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentConfigCatalog:
    async def test_catalog_returns_building_blocks(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.get("/api/v1/agent/configs/catalog")
        assert resp.status_code == 200
        body = resp.json()
        assert "specialists" in body
        assert "guardrails" in body
        assert "model_tiers" in body
        assert len(body["specialists"]) == 3
        assert len(body["guardrails"]) == 3
        assert len(body["model_tiers"]) == 3


class TestAgentConfigList:
    async def test_list_configs_empty(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get("/api/v1/agent/configs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["configs"] == []

    async def test_list_configs_with_domain_filter(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get(
            "/api/v1/agent/configs?domain=healthcare",
        )
        assert resp.status_code == 200
        # Verify the SQL included a WHERE clause for domain
        call_args = mock_pg.fetch.call_args
        assert "domain" in call_args[0][0].lower()


class TestAgentConfigCreate:
    async def test_create_config_success(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        resp = await client.post(
            "/api/v1/agent/configs",
            json={
                "name": "Test Config",
                "domain": "healthcare",
                "model_tier": "large",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Test Config"
        assert "id" in body
        mock_pg.execute.assert_called_once()

    async def test_create_config_defaults(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        resp = await client.post(
            "/api/v1/agent/configs",
            json={"name": "Minimal Config"},
        )
        assert resp.status_code == 201
        # Check the DB insert included default values
        call_args = mock_pg.execute.call_args[0]
        params = call_args[1]
        # specialists defaults to ["retrieval","analysis","action"]
        specialists = json.loads(params[5])
        assert "retrieval" in specialists

    async def test_create_config_invalid_tier(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/agent/configs",
            json={"name": "Bad", "model_tier": "mega"},
        )
        assert resp.status_code == 422

    async def test_create_config_missing_name(
        self, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/v1/agent/configs", json={},
        )
        assert resp.status_code == 422


class TestAgentConfigGet:
    async def test_get_config_found(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        cid = str(uuid.uuid4())
        mock_pg.fetch_one.return_value = FakeRecord({
            "id": cid,
            "name": "My Config",
            "domain": "industrial",
            "model_tier": "medium",
        })
        resp = await client.get(f"/api/v1/agent/configs/{cid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "My Config"

    async def test_get_config_not_found(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch_one.return_value = None
        resp = await client.get("/api/v1/agent/configs/nope")
        assert resp.status_code == 404


class TestAgentConfigUpdate:
    async def test_update_config_success(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        cid = str(uuid.uuid4())
        resp = await client.put(
            f"/api/v1/agent/configs/{cid}",
            json={"description": "Updated desc"},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    async def test_update_config_empty_body(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        cid = str(uuid.uuid4())
        resp = await client.put(
            f"/api/v1/agent/configs/{cid}", json={},
        )
        assert resp.status_code == 400


class TestAgentConfigDelete:
    async def test_delete_config(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        cid = str(uuid.uuid4())
        resp = await client.delete(f"/api/v1/agent/configs/{cid}")
        assert resp.status_code == 204
        mock_pg.execute.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Quality Evaluations CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestQualityEvaluationsList:
    async def test_list_evaluations_empty(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get("/api/v1/quality/evaluations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["evaluations"] == []

    async def test_list_evaluations_with_score_filter(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get(
            "/api/v1/quality/evaluations?min_score=3.0&max_score=5.0",
        )
        assert resp.status_code == 200
        # Verify the SQL included score filters
        call_args = mock_pg.fetch.call_args[0]
        assert "overall_score" in call_args[0]


class TestQualityMetrics:
    async def test_metrics_empty_db(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetchval.side_effect = [0, None]
        mock_pg.fetch.side_effect = [
            _records([{
                "avg_relevance": None,
                "avg_accuracy": None,
                "avg_completeness": None,
                "avg_conciseness": None,
                "avg_safety": None,
            }]),
            [],  # distribution
            [],  # trend
        ]
        resp = await client.get("/api/v1/quality/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_evaluations"] == 0
        assert body["average_score"] == 0


class TestQualityProposals:
    async def test_list_proposals_empty(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get("/api/v1/quality/proposals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["proposals"] == []

    async def test_list_proposals_filtered_by_status(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        mock_pg.fetchval.return_value = 0
        resp = await client.get(
            "/api/v1/quality/proposals?status=approved",
        )
        assert resp.status_code == 200
        call_args = mock_pg.fetch.call_args[0]
        assert "status" in call_args[0].lower()

    async def test_generate_proposal_no_evaluations(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        mock_pg.fetch.return_value = []
        resp = await client.post("/api/v1/quality/proposals/generate")
        assert resp.status_code == 404

    async def test_update_proposal_status(
        self, client: AsyncClient, mock_pg: AsyncMock,
    ) -> None:
        pid = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/quality/proposals/{pid}",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    async def test_update_proposal_invalid_status(
        self, client: AsyncClient,
    ) -> None:
        pid = str(uuid.uuid4())
        resp = await client.patch(
            f"/api/v1/quality/proposals/{pid}",
            json={"status": "invalid"},
        )
        assert resp.status_code == 422
