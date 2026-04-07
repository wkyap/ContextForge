"""Unit tests for the local subprocess sandbox backend."""

from __future__ import annotations

import pytest

from contextforge.evolution.sandbox_provider import SandboxConfig, SandboxProvider


@pytest.mark.asyncio
async def test_sandbox_executes_python_and_captures_stdout() -> None:
    provider = SandboxProvider()
    sid = await provider.create_sandbox()
    try:
        result = await provider.execute(sid, "print('hello from sandbox')")
        assert result.success is True
        assert "hello from sandbox" in result.stdout
        assert result.return_value == 0
        assert result.duration_ms >= 0
    finally:
        await provider.destroy_sandbox(sid)


@pytest.mark.asyncio
async def test_sandbox_captures_stderr_and_nonzero_exit() -> None:
    provider = SandboxProvider()
    sid = await provider.create_sandbox()
    try:
        result = await provider.execute(sid, "import sys; sys.exit(7)")
        assert result.success is False
        assert result.return_value == 7
        assert "exited with code 7" in (result.error or "")
    finally:
        await provider.destroy_sandbox(sid)


@pytest.mark.asyncio
async def test_sandbox_enforces_timeout() -> None:
    provider = SandboxProvider(default_config=SandboxConfig(timeout_seconds=1))
    sid = await provider.create_sandbox()
    try:
        result = await provider.execute(sid, "import time; time.sleep(5)")
        assert result.success is False
        assert "Timed out" in (result.error or "")
    finally:
        await provider.destroy_sandbox(sid)


@pytest.mark.asyncio
async def test_sandbox_rejects_non_python() -> None:
    provider = SandboxProvider()
    sid = await provider.create_sandbox()
    try:
        result = await provider.execute(sid, "echo hi", language="bash")
        assert result.success is False
        assert "only supports python" in (result.error or "")
    finally:
        await provider.destroy_sandbox(sid)


@pytest.mark.asyncio
async def test_sandbox_unknown_id() -> None:
    provider = SandboxProvider()
    result = await provider.execute("does-not-exist", "print(1)")
    assert result.success is False
    assert "not found" in (result.error or "")


@pytest.mark.asyncio
async def test_sandbox_destroy_cleans_workdir() -> None:
    provider = SandboxProvider()
    sid = await provider.create_sandbox()
    workdir = provider._workdirs[sid]
    assert workdir.exists()
    await provider.destroy_sandbox(sid)
    assert not workdir.exists()
    assert sid not in provider._active_sandboxes
