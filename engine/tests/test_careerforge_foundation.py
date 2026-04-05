"""CareerForge foundation tests — Sprint 1 API endpoints + PDPA guardrail.

Requires a running stack: ``docker compose up -d``
Run with: ``pytest tests/test_careerforge_foundation.py -v``
"""

from __future__ import annotations

import httpx
import pytest

BASE_URL = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, timeout=30)


# ── Trainees ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_trainees(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/trainees")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "trainees" in body
    assert isinstance(body["trainees"], list)


@pytest.mark.asyncio
async def test_create_and_get_trainee(client: httpx.AsyncClient) -> None:
    payload = {
        "trainee_code": "TEST-0001",
        "name": "Test Trainee",
        "email": "test@example.com",
        "education_level": "Diploma",
        "years_experience": 2,
        "career_goals": ["Software Developer"],
        "preferred_sectors": ["ICT"],
        "programme_type": "SCTP",
    }
    async with client:
        # Create
        resp = await client.post("/trainees", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["trainee_code"] == "TEST-0001"
        assert body["status"] == "applied"
        trainee_id = body["id"]

        # Get by ID
        resp2 = await client.get(f"/trainees/{trainee_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Test Trainee"

        # Get by code
        resp3 = await client.get("/trainees/TEST-0001")
        assert resp3.status_code == 200


@pytest.mark.asyncio
async def test_trainee_filter_by_status(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/trainees", params={"status": "applied"})
    assert resp.status_code == 200


# ── Courses ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_courses(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/courses")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "courses" in body


@pytest.mark.asyncio
async def test_create_course(client: httpx.AsyncClient) -> None:
    payload = {
        "course_code": "TEST-CRS-001",
        "title": "Test Course",
        "sector": "ICT",
        "duration_weeks": 12,
        "mode": "full-time",
        "skills_taught": ["Python", "SQL"],
    }
    async with client:
        resp = await client.post("/courses", json=payload)
        assert resp.status_code == 201
        assert resp.json()["course_code"] == "TEST-CRS-001"


# ── Employers ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_employers(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/employers")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "employers" in body


@pytest.mark.asyncio
async def test_create_employer(client: httpx.AsyncClient) -> None:
    payload = {
        "company_name": "Test Corp Pte Ltd",
        "uen": "99999999Z",
        "sector": "ICT",
        "size": "sme",
        "locations": ["Central"],
        "partnership_tier": "new",
    }
    async with client:
        resp = await client.post("/employers", json=payload)
        assert resp.status_code == 201
        assert resp.json()["company_name"] == "Test Corp Pte Ltd"


# ── Job Openings ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_openings(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/openings")
    assert resp.status_code == 200
    body = resp.json()
    assert "openings" in body


# ── Placements ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_placements(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/placements")
    assert resp.status_code == 200
    body = resp.json()
    assert "placements" in body


# ── Reports ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_metrics(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/reports/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert "kpi" in body
    assert "total_trainees" in body["kpi"]
    assert "placement_rate" in body["kpi"]


@pytest.mark.asyncio
async def test_at_risk_trainees(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/reports/at-risk")
    assert resp.status_code == 200
    body = resp.json()
    assert "at_risk_count" in body
    assert "trainees" in body


@pytest.mark.asyncio
async def test_placement_funnel(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.get("/reports/placement-funnel")
    assert resp.status_code == 200
    body = resp.json()
    assert "funnel" in body
    for status in ["applied", "enrolled", "training", "completed", "placed"]:
        assert status in body["funnel"]


@pytest.mark.asyncio
async def test_ssg_report(client: httpx.AsyncClient) -> None:
    async with client:
        resp = await client.post("/reports/ssg")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_type"] == "ssg_monthly"
    assert body["requires_signoff"] is True


# ── PDPA Guardrail (unit-style, no server needed) ───────────────────────────

def test_pdpa_nric_detection() -> None:
    from contextforge.guardrails.pdpa_sg import detect_pdpa_pii, redact_pdpa

    text = "Trainee NRIC is S1234567A and phone is 91234567."
    findings = detect_pdpa_pii(text)
    types = {f["type"] for f in findings}
    assert "sg_nric" in types
    assert "sg_phone" in types

    redacted = redact_pdpa(text)
    assert "S1234567A" not in redacted
    assert "91234567" not in redacted


def test_pdpa_nric_masking() -> None:
    from contextforge.guardrails.pdpa_sg import mask_nric_display, hash_nric

    masked = mask_nric_display("S1234567A")
    assert masked == "S****567A"

    hashed = hash_nric("S1234567A")
    assert len(hashed) == 64  # SHA-256 hex
    # Same input should produce same hash
    assert hash_nric("S1234567A") == hashed
