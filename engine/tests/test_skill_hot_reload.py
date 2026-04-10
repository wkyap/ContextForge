"""Offline tests for SkillRegistry.reload_file + watch_skills."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from contextforge.skills.registry import SkillRegistry
from contextforge.skills.watcher import watch_skills

VALID_SKILL = """\
---
name: {name}
type: knowledge
domain: _test
version: "1.0.0"
description: {desc}
---

# {name}
"""

CONNECTOR_SKILL = """\
---
name: {name}
type: connector
domain: _test
version: "1.0.0"
description: test connector
source_kind: http_poll
config:
  url: https://example.com
---

# body
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def reg(tmp_path: Path) -> SkillRegistry:
    return SkillRegistry(root=tmp_path, lazy=True)


def test_reload_file_registers_new_skill(tmp_path: Path, reg: SkillRegistry) -> None:
    f = tmp_path / "alpha.md"
    _write(f, VALID_SKILL.format(name="alpha", desc="first version"))
    skill = reg.reload_file(f)
    assert skill is not None
    assert skill.name == "alpha"
    assert reg.get("alpha") is not None
    assert "alpha" in [s.name for s in reg.list_by_type("knowledge")]


def test_reload_file_replaces_existing_entry(tmp_path: Path, reg: SkillRegistry) -> None:
    f = tmp_path / "beta.md"
    _write(f, VALID_SKILL.format(name="beta", desc="v1"))
    reg.reload_file(f)
    # Edit on disk and re-trigger reload.
    _write(f, VALID_SKILL.format(name="beta", desc="v2 updated"))
    reg.reload_file(f)
    skill = reg.get("beta")
    assert skill is not None
    assert "v2 updated" in skill.description
    # No duplicates in the type index.
    knowledge = reg.list_by_type("knowledge")
    assert sum(1 for s in knowledge if s.name == "beta") == 1


def test_reload_file_removes_skill_when_file_deleted(
    tmp_path: Path, reg: SkillRegistry
) -> None:
    f = tmp_path / "gamma.md"
    _write(f, VALID_SKILL.format(name="gamma", desc="x"))
    reg.reload_file(f)
    assert reg.get("gamma") is not None
    f.unlink()
    result = reg.reload_file(f)
    assert result is None
    assert reg.get("gamma") is None
    assert all(s.name != "gamma" for s in reg.list_by_type("knowledge"))


def test_reload_file_rejects_invalid_skill(tmp_path: Path, reg: SkillRegistry) -> None:
    f = tmp_path / "broken.md"
    # Missing required fields → validator should reject.
    _write(f, "---\nname: broken\ntype: not_a_real_type\n---\n\nbody")
    result = reg.reload_file(f)
    assert result is None
    assert reg.get("broken") is None


def test_reload_file_handles_unparseable_yaml(tmp_path: Path, reg: SkillRegistry) -> None:
    f = tmp_path / "garbage.md"
    _write(f, "---\nname: [unterminated\n---\nbody")
    result = reg.reload_file(f)
    assert result is None


def test_reload_file_changes_skill_type_correctly(
    tmp_path: Path, reg: SkillRegistry
) -> None:
    f = tmp_path / "delta.md"
    _write(f, VALID_SKILL.format(name="delta", desc="knowledge first"))
    reg.reload_file(f)
    assert reg.get("delta").type == "knowledge"  # type: ignore[union-attr]

    # Convert it into a connector skill.
    _write(f, CONNECTOR_SKILL.format(name="delta"))
    reg.reload_file(f)
    skill = reg.get("delta")
    assert skill is not None
    assert skill.type == "connector"
    # Old type bucket no longer references it.
    assert all(s.name != "delta" for s in reg.list_by_type("knowledge"))
    assert "delta" in [s.name for s in reg.list_by_type("connector")]


@pytest.mark.asyncio
async def test_watch_skills_picks_up_new_file(tmp_path: Path) -> None:
    """The async watcher should register a brand-new SKILL.md it observes."""
    reg = SkillRegistry(root=tmp_path, lazy=True)
    # Trigger lazy load with empty dir.
    reg.load_from_directory(tmp_path)
    assert reg.get("epsilon") is None

    stop = asyncio.Event()
    watcher = asyncio.create_task(watch_skills(reg, tmp_path, stop))
    try:
        # Give the watcher a moment to start observing.
        await asyncio.sleep(0.2)
        f = tmp_path / "epsilon.md"
        _write(f, VALID_SKILL.format(name="epsilon", desc="watched in"))

        # Poll for the registration with a timeout.
        for _ in range(50):
            if reg.get("epsilon") is not None:
                break
            await asyncio.sleep(0.1)

        assert reg.get("epsilon") is not None, "watcher did not pick up new skill"
    finally:
        stop.set()
        watcher.cancel()
        try:
            await watcher
        except (asyncio.CancelledError, Exception):
            pass


@pytest.mark.asyncio
async def test_watch_skills_picks_up_modification(tmp_path: Path) -> None:
    reg = SkillRegistry(root=tmp_path, lazy=True)
    f = tmp_path / "zeta.md"
    _write(f, VALID_SKILL.format(name="zeta", desc="initial"))
    reg.load_from_directory(tmp_path)
    assert reg.get("zeta").description == "initial"  # type: ignore[union-attr]

    stop = asyncio.Event()
    watcher = asyncio.create_task(watch_skills(reg, tmp_path, stop))
    try:
        await asyncio.sleep(0.2)
        _write(f, VALID_SKILL.format(name="zeta", desc="modified by watcher"))

        for _ in range(50):
            s = reg.get("zeta")
            if s and "modified" in s.description:
                break
            await asyncio.sleep(0.1)

        assert "modified" in reg.get("zeta").description  # type: ignore[union-attr]
    finally:
        stop.set()
        watcher.cancel()
        try:
            await watcher
        except (asyncio.CancelledError, Exception):
            pass
