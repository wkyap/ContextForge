"""Tests for connector sandboxing."""

from __future__ import annotations

import pytest

from contextforge.connectors.sandbox import SandboxedConnector, SandboxLimits


@pytest.mark.asyncio
async def test_sandboxed_connector_health_before_connect() -> None:
    """Health should report 'stopped' before connect is called."""
    sc = SandboxedConnector(
        name="test",
        driver_module="contextforge.connectors.drivers.http_poll",
        driver_class="HTTPPollConnector",
        config={"url": "http://localhost:9999/nope"},
    )
    h = sc.health()
    assert h.status.value == "stopped"
    assert h.records_emitted == 0


def test_sandbox_limits_defaults() -> None:
    lim = SandboxLimits()
    assert lim.timeout_seconds == 300
    assert lim.max_records_per_batch == 1000
    assert lim.max_memory_mb == 512
    assert lim.restart_on_failure is True
    assert lim.max_restarts == 3


def test_sandbox_limits_custom() -> None:
    lim = SandboxLimits(timeout_seconds=60, max_restarts=1)
    assert lim.timeout_seconds == 60
    assert lim.max_restarts == 1


def test_wrapper_script_generated() -> None:
    sc = SandboxedConnector(
        name="test-driver",
        driver_module="contextforge.connectors.drivers.mqtt",
        driver_class="MQTTConnector",
        config={"broker": "localhost"},
    )
    script = sc._build_wrapper_script()
    assert "from contextforge.connectors.drivers.mqtt import MQTTConnector" in script
    assert '"type": "ready"' in script
    assert '"type": "record"' in script


@pytest.mark.asyncio
async def test_sandboxed_connector_close_without_connect() -> None:
    """Close should be safe to call even if never connected."""
    sc = SandboxedConnector(
        name="test",
        driver_module="contextforge.connectors.drivers.http_poll",
        driver_class="HTTPPollConnector",
        config={},
    )
    await sc.close()  # Should not raise
    assert sc.health().status.value == "stopped"
