"""SkillRegistry — scan, catalog, cache, and look up skills."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from contextforge.skills.loader import Skill, load_skill, scan_directory
from contextforge.skills.validator import validate_skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """In-memory registry of all loaded skills.

    Supports lazy loading (skills are not parsed until first access) and
    hot-reload (single-file re-registration via `reload_file`).
    """

    def __init__(self, root: Path | None = None, lazy: bool = True) -> None:
        self._by_name: dict[str, Skill] = {}
        self._by_type: dict[str, list[Skill]] = {}
        self._by_domain: dict[str, list[Skill]] = {}
        self._root: Path | None = root
        self._loaded: bool = False
        if root is not None and not lazy:
            self.load_from_directory(root)

    # ── Loading ───────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._loaded or self._root is None:
            return
        self.load_from_directory(self._root)

    def load_from_directory(self, root: Path) -> int:
        """Scan a directory tree and register all valid skills. Returns count loaded."""
        self._root = root
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
        self._loaded = True
        logger.info("Registry loaded %d skills from %s", loaded, root)
        return loaded

    def reload_file(self, path: Path) -> Skill | None:
        """Re-parse a single SKILL.md file and replace its registry entry.

        Returns the new Skill on success, None if the file is missing or invalid.
        Used by the hot-reload watcher.
        """
        if not path.exists():
            # File deleted — remove any matching entry by file_path.
            removed = self._remove_by_path(str(path))
            if removed:
                logger.info("Hot-reload: removed skill from %s", path)
            return None
        try:
            skill = load_skill(path)
        except Exception:
            logger.warning("Hot-reload: failed to parse %s", path, exc_info=True)
            return None
        result = validate_skill(skill)
        if not result.valid:
            logger.warning("Hot-reload: invalid skill %s: %s", skill.name, result.errors)
            return None
        # Drop any prior entry for this same file path before re-registering.
        self._remove_by_path(str(path))
        self.register(skill)
        logger.info("Hot-reload: registered %s (%s) from %s", skill.name, skill.type, path)
        return skill

    def _remove_by_path(self, file_path: str) -> bool:
        match = next(
            (s for s in self._by_name.values() if s.file_path == file_path), None
        )
        if match is None:
            return False
        self._by_name.pop(match.name, None)
        if match in self._by_type.get(match.type, []):
            self._by_type[match.type].remove(match)
        if match in self._by_domain.get(match.domain, []):
            self._by_domain[match.domain].remove(match)
        return True

    def register(self, skill: Skill) -> None:
        """Add or replace a skill in the registry."""
        # If a skill with this name already exists, drop it from index lists first.
        prior = self._by_name.get(skill.name)
        if prior is not None:
            if prior in self._by_type.get(prior.type, []):
                self._by_type[prior.type].remove(prior)
            if prior in self._by_domain.get(prior.domain, []):
                self._by_domain[prior.domain].remove(prior)
        self._by_name[skill.name] = skill
        self._by_type.setdefault(skill.type, []).append(skill)
        self._by_domain.setdefault(skill.domain, []).append(skill)

    # ── Lookup ────────────────────────────────────────────────────────────

    def get(self, name: str) -> Skill | None:
        self._ensure_loaded()
        return self._by_name.get(name)

    def list_all(self) -> list[Skill]:
        self._ensure_loaded()
        return list(self._by_name.values())

    def list_by_type(self, skill_type: str) -> list[Skill]:
        self._ensure_loaded()
        return self._by_type.get(skill_type, [])

    def list_by_domain(self, domain: str) -> list[Skill]:
        self._ensure_loaded()
        return self._by_domain.get(domain, [])

    def list_names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._by_name.keys())

    @property
    def count(self) -> int:
        self._ensure_loaded()
        return len(self._by_name)

    @property
    def root(self) -> Path | None:
        return self._root

    # ── Serialization ─────────────────────────────────────────────────────

    def to_catalog(self) -> list[dict[str, Any]]:
        """Return a lightweight catalog for API responses."""
        self._ensure_loaded()
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
