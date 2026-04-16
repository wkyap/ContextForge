"""Filesystem watcher for hot-reloading SKILL.md files into the registry."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchfiles import Change, awatch

from contextforge.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


async def watch_skills(registry: SkillRegistry, root: Path, stop: asyncio.Event) -> None:
    """Watch `root` for SKILL.md changes and re-register affected skills.

    Designed to run as a background task. Cancellation or `stop.set()` exits cleanly.
    """
    logger.info("Skill hot-reload watcher started on %s", root)
    try:
        async for changes in awatch(root, stop_event=stop, recursive=True):
            for change, raw_path in changes:
                path = Path(raw_path)
                if path.suffix.lower() != ".md" or path.name.startswith("README"):
                    continue
                if change == Change.deleted:
                    registry.reload_file(path)  # path missing → removal
                else:
                    registry.reload_file(path)
    except asyncio.CancelledError:
        logger.info("Skill hot-reload watcher cancelled")
        raise
    except Exception:
        logger.exception("Skill hot-reload watcher crashed")
