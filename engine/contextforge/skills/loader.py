"""SKILL.md file parser — YAML frontmatter + markdown body."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """Parsed representation of a single SKILL.md file."""

    name: str
    type: str
    domain: str
    version: int
    description: str
    file_path: str
    author: str = "human"
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def search_text(self) -> str:
        """Combined text for embedding generation."""
        parts = [self.name, self.description]
        parts.extend(self.tags)
        if self.body:
            parts.append(self.body[:2000])
        return " ".join(parts)


def load_skill(path: Path) -> Skill:
    """Parse a single SKILL.md file into a Skill object."""
    text = path.read_text(encoding="utf-8")
    post = frontmatter.loads(text)

    meta = dict(post.metadata)
    name = meta.pop("name", path.stem)
    skill_type = meta.pop("type", "knowledge")
    domain = meta.pop("domain", "unknown")
    version = int(meta.pop("version", 1))
    description = meta.pop("description", "")
    author = meta.pop("author", "human")
    tags = meta.pop("tags", [])

    return Skill(
        name=name,
        type=skill_type,
        domain=domain,
        version=version,
        description=description,
        file_path=str(path),
        author=author,
        tags=tags if isinstance(tags, list) else [tags],
        metadata=meta,
        body=post.content.strip(),
    )


def scan_directory(root: Path) -> list[Skill]:
    """Recursively scan a directory for SKILL.md files and parse them all."""
    skills: list[Skill] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.startswith("README"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                skill = load_skill(path)
                skills.append(skill)
                logger.debug("Loaded skill: %s (%s)", skill.name, skill.type)
        except Exception:
            logger.warning("Failed to parse skill file: %s", path, exc_info=True)
    logger.info("Scanned %s — found %d skills", root, len(skills))
    return skills
