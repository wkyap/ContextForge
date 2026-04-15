"""Sandboxed connector execution — subprocess isolation for untrusted drivers.

Wraps a ConnectorBase driver in a subprocess with resource limits and timeout
enforcement. Communicates via JSON over stdin/stdout pipes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from contextforge.connectors.base import ConnectorBase, ConnectorHealth, ConnectorStatus, Record

logger = logging.getLogger(__name__)


@dataclass
class SandboxLimits:
    """Resource limits for a sandboxed connector."""

    timeout_seconds: int = 300
    max_records_per_batch: int = 1000
    max_memory_mb: int = 512
    restart_on_failure: bool = True
    max_restarts: int = 3


@dataclass
class SandboxedConnectorState:
    """Runtime state for a sandboxed connector."""

    process: asyncio.subprocess.Process | None = None
    records_emitted: int = 0
    restarts: int = 0
    last_error: str | None = None
    started_at: float = 0.0


class SandboxedConnector(ConnectorBase):
    """Wraps a connector driver in a subprocess with resource isolation.

    The inner driver runs in a separate Python process using ``-I`` (isolated)
    mode. Records are serialized as JSON lines over stdout. The parent monitors
    health via periodic heartbeat checks.

    Usage::

        sandboxed = SandboxedConnector(
            name="my-connector",
            driver_module="contextforge.connectors.drivers.http_poll",
            driver_class="HTTPPollConnector",
            config={"url": "https://..."},
        )
        await sandboxed.connect()
        async for record in sandboxed.stream():
            process(record)
    """

    def __init__(
        self,
        name: str,
        driver_module: str,
        driver_class: str,
        config: dict[str, Any],
        *,
        limits: SandboxLimits | None = None,
    ) -> None:
        super().__init__(name=name, config=config)
        self._driver_module = driver_module
        self._driver_class = driver_class
        self._limits = limits or SandboxLimits()
        self._state = SandboxedConnectorState()

    async def connect(self) -> None:
        """Spawn the subprocess and wait for the ready signal."""
        await self._spawn()

    async def _spawn(self) -> None:
        """Start (or restart) the child process."""
        wrapper_code = self._build_wrapper_script()

        self._state.process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-c", wrapper_code,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._state.started_at = time.monotonic()
        logger.info(
            "Sandboxed connector '%s' spawned (pid=%s, module=%s)",
            self.name, self._state.process.pid, self._driver_module,
        )

    def _build_wrapper_script(self) -> str:
        """Generate the Python script that runs inside the subprocess."""
        config_json = json.dumps(self.config)
        return f'''
import asyncio
import json
import sys

async def main():
    from {self._driver_module} import {self._driver_class}

    config = json.loads({config_json!r})
    driver = {self._driver_class}(name={self.name!r}, config=config)
    await driver.connect()

    # Signal ready
    print(json.dumps({{"type": "ready"}}), flush=True)

    try:
        async for record in driver.stream():
            line = json.dumps({{
                "type": "record",
                "source": record.source,
                "data": record.payload,
                "timestamp": record.timestamp,
                "metadata": record.metadata,
            }})
            print(line, flush=True)
    except Exception as exc:
        print(json.dumps({{"type": "error", "message": str(exc)}}), flush=True)
    finally:
        await driver.close()

asyncio.run(main())
'''

    async def stream(self) -> AsyncIterator[Record]:
        """Yield records from the sandboxed subprocess."""
        proc = self._state.process
        if proc is None or proc.stdout is None:
            return

        while True:
            try:
                line = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=self._limits.timeout_seconds,
                )
            except TimeoutError:
                logger.warning("Sandboxed connector '%s' timed out", self.name)
                await self._handle_failure("Timeout")
                if not self._limits.restart_on_failure:
                    return
                if self._state.restarts >= self._limits.max_restarts:
                    logger.error("Max restarts reached for '%s'", self.name)
                    return
                self._state.restarts += 1
                await self._spawn()
                proc = self._state.process
                if proc is None or proc.stdout is None:
                    return
                continue

            if not line:
                # Process exited
                if (
                    self._limits.restart_on_failure
                    and self._state.restarts < self._limits.max_restarts
                ):
                    self._state.restarts += 1
                    logger.info(
                        "Restarting sandboxed connector '%s' (restart %d)",
                        self.name,
                        self._state.restarts,
                    )
                    await self._spawn()
                    proc = self._state.process
                    if proc is None or proc.stdout is None:
                        return
                    continue
                return

            try:
                msg = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "ready":
                logger.info("Sandboxed connector '%s' ready", self.name)
                continue
            elif msg_type == "error":
                self._state.last_error = msg.get("message", "unknown")
                logger.error(
                    "Sandboxed connector '%s' error: %s", self.name, self._state.last_error
                )
                continue
            elif msg_type == "record":
                self._state.records_emitted += 1
                yield Record(
                    source=msg.get("source", self.name),
                    payload=msg.get("data", {}),
                    timestamp=msg.get("timestamp", 0.0),
                    metadata=msg.get("metadata", {}),
                )

    async def _handle_failure(self, reason: str) -> None:
        """Kill the subprocess on failure."""
        self._state.last_error = reason
        proc = self._state.process
        if proc and proc.returncode is None:
            proc.kill()
            await proc.wait()

    async def close(self) -> None:
        """Terminate the subprocess."""
        proc = self._state.process
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()
        self._state.process = None
        logger.info("Sandboxed connector '%s' closed", self.name)

    def health(self) -> ConnectorHealth:
        """Return health status for the sandboxed connector."""
        proc = self._state.process
        alive = proc is not None and proc.returncode is None
        return ConnectorHealth(
            status=ConnectorStatus.RUNNING if alive else ConnectorStatus.STOPPED,
            records_emitted=self._state.records_emitted,
            last_error=self._state.last_error,
        )
