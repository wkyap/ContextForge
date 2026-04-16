"""SKILL.md to PydanticAI Capability converter.

Bridges the markdown-based skill system to PydanticAI's typed agent
capabilities.  Domain experts write SKILL.md, the Tool Forge agent
generates the Python Capability class, and the Capability plugs into
any PydanticAI agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

logger = logging.getLogger(__name__)


@dataclass
class SkillCapability:
    """A PydanticAI-compatible capability generated from a SKILL.md file.

    Wraps the skill's instructions and metadata so that a PydanticAI
    agent can dynamically acquire domain-specific behaviour at runtime.
    """

    name: str
    description: str
    instructions: str
    skill_type: str
    domain: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    mcp_server: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_skill_file(path: str | Path) -> SkillCapability:
    """Parse a SKILL.md file into a ``SkillCapability``."""
    post = frontmatter.load(str(path))
    meta = post.metadata

    return SkillCapability(
        name=meta.get("name", Path(path).stem),
        description=meta.get("description", ""),
        instructions=post.content,
        skill_type=meta.get("type", "computation"),
        domain=meta.get("domain", "general"),
        inputs=meta.get("inputs", []),
        outputs=meta.get("outputs", []),
        mcp_server=meta.get("mcp_server"),
        metadata={
            k: v
            for k, v in meta.items()
            if k not in {"name", "description", "type", "domain", "inputs", "outputs", "mcp_server"}
        },
    )


def skill_to_agent_instructions(capability: SkillCapability) -> str:
    """Format a SkillCapability as additional agent instructions."""
    parts = [
        f"## Skill: {capability.name}",
        f"Type: {capability.skill_type}",
        f"Domain: {capability.domain}",
        "",
        capability.instructions,
    ]
    if capability.mcp_server:
        parts.insert(3, f"MCP Server: {capability.mcp_server}")
    return "\n".join(parts)


def load_domain_capabilities(domain_dir: str | Path) -> list[SkillCapability]:
    """Scan a domain directory and parse all SKILL.md files."""
    domain_path = Path(domain_dir)
    capabilities: list[SkillCapability] = []

    if not domain_path.exists():
        logger.warning("Domain directory does not exist: %s", domain_dir)
        return capabilities

    for skill_file in domain_path.rglob("*.skill.md"):
        try:
            capabilities.append(parse_skill_file(skill_file))
        except Exception:
            logger.exception("Failed to parse skill file: %s", skill_file)

    # Also match SKILL.md naming convention
    for skill_file in domain_path.rglob("*SKILL.md"):
        if skill_file not in [Path(c.metadata.get("_path", "")) for c in capabilities]:
            try:
                capabilities.append(parse_skill_file(skill_file))
            except Exception:
                logger.exception("Failed to parse skill file: %s", skill_file)

    logger.info("Loaded %d capabilities from %s", len(capabilities), domain_dir)
    return capabilities
