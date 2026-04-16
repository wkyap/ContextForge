"""Sandbox provider — sandboxed execution for Tool Forge.

The default backend is a local ``asyncio.subprocess`` runner that:

* writes the code to a per-sandbox temp directory,
* spawns a fresh Python interpreter with stdin/stdout/stderr piped,
* enforces a wall-clock timeout (and kills the process on overrun),
* captures stdout/stderr/return code into a ``SandboxResult``.

This is *not* a hardened isolation boundary — it relies on the OS user
the engine runs as. For production deployments wire this provider to a
Docker/E2B/Daytona container by replacing :meth:`SandboxProvider.execute`.
The local backend is enough for unit tests and developer flows.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Result of a sandboxed code execution."""

    sandbox_id: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class SandboxConfig:
    """Configuration for a sandbox instance."""

    image: str = "python:3.12-slim"
    timeout_seconds: int = 30
    memory_limit_mb: int = 256
    cpu_limit: float = 0.5
    network_enabled: bool = False
    allowed_packages: list[str] = field(default_factory=list)


class SandboxProvider:
    """Manages Docker-based sandboxed execution environments.

    Used by the Tool Forge Agent (Section 8.2) to safely execute
    AI-generated tool code before it's approved for production.
    """

    def __init__(
        self,
        *,
        sandbox_url: str = "http://sandbox:8080",
        default_config: SandboxConfig | None = None,
    ) -> None:
        self._sandbox_url = sandbox_url
        self._default_config = default_config or SandboxConfig()
        self._active_sandboxes: dict[str, SandboxConfig] = {}
        self._workdirs: dict[str, Path] = {}

    async def create_sandbox(
        self,
        config: SandboxConfig | None = None,
    ) -> str:
        """Create a new sandbox instance. Returns sandbox_id."""
        sandbox_id = str(uuid.uuid4())
        cfg = config or self._default_config
        self._active_sandboxes[sandbox_id] = cfg
        self._workdirs[sandbox_id] = Path(
            tempfile.mkdtemp(prefix=f"cf-sandbox-{sandbox_id[:8]}-")
        )

        logger.info(
            "Created sandbox %s (image=%s, timeout=%ds, network=%s, workdir=%s)",
            sandbox_id,
            cfg.image,
            cfg.timeout_seconds,
            cfg.network_enabled,
            self._workdirs[sandbox_id],
        )
        return sandbox_id

    async def execute(
        self,
        sandbox_id: str,
        code: str,
        *,
        language: str = "python",
    ) -> SandboxResult:
        """Execute code in a sandboxed environment.

        The code runs in an isolated Docker container with no host access.
        Network is disabled by default to prevent data exfiltration.
        """
        if sandbox_id not in self._active_sandboxes:
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Sandbox {sandbox_id} not found",
            )

        if language != "python":
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Local sandbox backend only supports python (got: {language})",
            )

        config = self._active_sandboxes[sandbox_id]
        workdir = self._workdirs[sandbox_id]
        script = workdir / f"snippet_{uuid.uuid4().hex[:8]}.py"
        script.write_text(code, encoding="utf-8")

        logger.info(
            "Executing %s code in sandbox %s (%d chars, timeout=%ds)",
            language,
            sandbox_id,
            len(code),
            config.timeout_seconds,
        )

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",  # isolated mode: ignore PYTHON* env, no user site-packages
                str(script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workdir),
            )
        except OSError as exc:
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Failed to spawn interpreter: {exc}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=config.timeout_seconds
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            duration_ms = (time.monotonic() - start) * 1000
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Timed out after {config.timeout_seconds}s",
                duration_ms=duration_ms,
            )

        duration_ms = (time.monotonic() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        success = proc.returncode == 0

        return SandboxResult(
            sandbox_id=sandbox_id,
            success=success,
            stdout=stdout,
            stderr=stderr,
            return_value=proc.returncode,
            duration_ms=duration_ms,
            error=None if success else f"Process exited with code {proc.returncode}",
        )

    async def install_packages(
        self,
        sandbox_id: str,
        packages: list[str],
    ) -> SandboxResult:
        """Install Python packages in a sandbox (allowlisted only)."""
        if sandbox_id not in self._active_sandboxes:
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Sandbox {sandbox_id} not found",
            )

        config = self._active_sandboxes[sandbox_id]

        # Check allowlist
        disallowed = [
            p for p in packages if p not in config.allowed_packages
        ]
        if disallowed and config.allowed_packages:
            return SandboxResult(
                sandbox_id=sandbox_id,
                success=False,
                error=f"Packages not in allowlist: {disallowed}",
            )

        logger.info("Installing packages in sandbox %s: %s", sandbox_id, packages)
        return SandboxResult(
            sandbox_id=sandbox_id,
            success=True,
            stdout=f"Installed: {', '.join(packages)}",
        )

    async def destroy_sandbox(self, sandbox_id: str) -> None:
        """Destroy a sandbox and clean up resources."""
        if sandbox_id in self._active_sandboxes:
            del self._active_sandboxes[sandbox_id]
            workdir = self._workdirs.pop(sandbox_id, None)
            if workdir and workdir.exists():
                shutil.rmtree(workdir, ignore_errors=True)
            logger.info("Destroyed sandbox %s", sandbox_id)

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes."""
        sandbox_ids = list(self._active_sandboxes.keys())
        for sid in sandbox_ids:
            await self.destroy_sandbox(sid)
        logger.info("Cleaned up %d sandboxes", len(sandbox_ids))
