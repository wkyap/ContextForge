"""SkillRegistry — scan, catalog, cache, and look up skills."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from contextforge.skills.loader import Skill, scan_directory
from contextforge.skills.validator import validate_skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """In-memory registry of all loaded skills."""

    def __init__(self) -> None:
        self._by_name: dict[str, Skill] = {}
        self._by_type: dict[str, list[Skill]] = {}
        self._by_domain: dict[str, list[Skill]] = {}

    # ── Loading ───────────────────────────────────────────────────────────

    def load_from_directory(self, root: Path) -> int:
        """Scan a directory tree and register all valid skills. Returns count loaded."""
        skills = scan_directory(root)
        loaded = 0
        for skill in skills:
            result = validate_skill(skill)
            if not result.valid:
                logger.warning(
                    "Skipping invalid skill %s: %s", skill.name, result.errors
                )
                continue
            if result.warnings:
                logger.info("Skill %s warnings: %s", skill.name, result.warnings)
            self.register(skill)
            loaded += 1
        logger.info("Registry loaded %d skills from %s", loaded, root)
        return loaded

    def register(self, skill: Skill) -> None:
        """Add or replace a skill in the registry."""
        self._by_name[skill.name] = skill
        self._by_type.setdefault(skill.type, []).append(skill)
        self._by_domain.setdefault(skill.domain, []).append(skill)

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, name: str) -> Skill | None:
        return self._by_name.get(name)

    def list_all(self) -> list[Skill]:
        return list(self._by_name.values())

    def list_by_type(self, skill_type: str) -> list[Skill]:
        return self._by_type.get(skill_type, [])

    def list_by_domain(self, domain: str) -> list[Skill]:
        return self._by_domain.get(domain, [])

    def list_names(self) -> list[str]:
        return sorted(self._by_name.keys())

    @property
    def count(self) -> int:
        return len(self._by_name)

    # ── Serialization ─────────────────────────────────────────────────────

    def to_catalog(self) -> list[dict[str, Any]]:
        """Return a lightweight catalog for API responses."""
        return [
            {
                "name": s.name,
                "type": s.type,
                "domain": s.domain,
                "version": s.version,
                "description": s.description,
                "author": s.author,
                "tags": s.tags,
            }
            for s in self._by_name.values()
        ]
