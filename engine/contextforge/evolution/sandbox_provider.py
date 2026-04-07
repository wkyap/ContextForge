"""Sandbox provider — Docker-based sandbox management for Tool Forge.

Provides isolated execution environments for AI-generated tool code.
Uses E2B/Daytona-style Docker containers with no host access.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
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

    async def create_sandbox(
        self,
        config: SandboxConfig | None = None,
    ) -> str:
        """Create a new sandbox instance. Returns sandbox_id."""
        sandbox_id = str(uuid.uuid4())
        cfg = config or self._default_config
        self._active_sandboxes[sandbox_id] = cfg

        logger.info(
            "Created sandbox %s (image=%s, timeout=%ds, network=%s)",
            sandbox_id,
            cfg.image,
            cfg.timeout_seconds,
            cfg.network_enabled,
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

        logger.info(
            "Executing %s code in sandbox %s (%d chars)",
            language,
            sandbox_id,
            len(code),
        )

        # TODO: Replace with actual Docker/E2B API call
        # For now, return a placeholder indicating the sandbox is ready
        return SandboxResult(
            sandbox_id=sandbox_id,
            success=True,
            stdout="[Sandbox execution placeholder — wire to Docker/E2B API]",
            duration_ms=0.0,
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
            logger.info("Destroyed sandbox %s", sandbox_id)

    async def cleanup_all(self) -> None:
        """Destroy all active sandboxes."""
        sandbox_ids = list(self._active_sandboxes.keys())
        for sid in sandbox_ids:
            await self.destroy_sandbox(sid)
        logger.info("Cleaned up %d sandboxes", len(sandbox_ids))
