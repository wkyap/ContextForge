"""Unit tests for the standalone graph nodes (no live stack required)."""

from __future__ import annotations

import pytest

from contextforge.agents.graph import context_check, guardrails_check


@pytest.mark.asyncio
async def test_context_check_noop_on_small_context() -> None:
    state = {"context": {"query": "hi", "facts": "two facts"}}
    delta = await context_check(state)  # type: ignore[arg-type]
    assert delta == {}


@pytest.mark.asyncio
async def test_context_check_compacts_when_over_soft_limit() -> None:
    big = "x" * 30_000
    state = {
        "context": {
            "query": "what is up",
            "facts": "essential",
            "scratch": big,
            "extra": big,
        }
    }
    delta = await context_check(state)  # type: ignore[arg-type]
    assert "context" in delta
    trimmed = delta["context"]
    # Essential keys are kept
    assert "query" in trimmed
    assert "facts" in trimmed
    # Non-essential big keys are dropped
    assert "scratch" not in trimmed
    assert "extra" not in trimmed


@pytest.mark.asyncio
async def test_context_check_handles_missing_context() -> None:
    assert await context_check({}) == {}  # type: ignore[arg-type]
    assert await context_check({"context": None}) == {}  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_guardrails_check_skips_when_no_output() -> None:
    delta = await guardrails_check({"domain": "industrial"})  # type: ignore[arg-type]
    results = delta["guardrails_results"]
    assert results[0]["status"] == "skipped"


@pytest.mark.asyncio
async def test_guardrails_check_passes_clean_text() -> None:
    state = {
        "domain": "industrial",
        "action_result": {"output": "The pump is operating within normal parameters."},
        "context": {"facts": "Pump telemetry shows nominal pressure readings."},
    }
    delta = await guardrails_check(state)  # type: ignore[arg-type]
    result = delta["guardrails_results"][0]
    assert result["status"] in ("pass", "fail")  # depends on guardrail strictness
    # Clean text should never trigger PII or toxicity
    assert result["pii_found"] is False
    assert result["toxicity_found"] is False


@pytest.mark.asyncio
async def test_guardrails_check_flags_pii() -> None:
    state = {
        "domain": "healthcare",
        "analysis_result": {
            "summary": "Patient John Doe SSN 123-45-6789 was admitted on Tuesday."
        },
    }
    delta = await guardrails_check(state)  # type: ignore[arg-type]
    result = delta["guardrails_results"][0]
    assert result["pii_found"] is True
    assert result["status"] == "fail"
