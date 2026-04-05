"""Skill-based ingester — dynamically maps data using SKILL.md instructions."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

from contextforge.ingestion.base_ingester import BaseIngester, IngestResult
from contextforge.knowledge.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)


@dataclass
class MappingRule:
    """A single source-field to graph-element mapping parsed from a skill."""

    source_path: str
    target_type: str  # "entity" or "relationship"
    target_label: str
    property_map: dict[str, str] = field(default_factory=dict)


@dataclass
class IngestionSkill:
    """Parsed ingestion skill with mapping rules and metadata."""

    name: str
    domain: str
    version: int
    description: str
    source_format: str
    entity_mappings: list[MappingRule] = field(default_factory=list)
    relationship_mappings: list[MappingRule] = field(default_factory=list)
    body: str = ""


class SkillBasedIngester(BaseIngester):
    """Ingest arbitrary domain data using mapping rules from SKILL.md files.

    Instead of hard-coding field mappings, this ingester reads a skill file
    that declares *how* to transform source data into graph entities and
    relationships.  New domains can be supported by adding a skill file
    without any code changes.
    """

    def __init__(self, graph: TemporalGraph, skill_path: Path) -> None:
        self._graph = graph
        self._skill = self._load_skill(skill_path)
        super().__init__(source_name=f"skill:{self._skill.name}")

    # ── Skill loading ─────────────────────────────────────────────────────

    @staticmethod
    def _load_skill(path: Path) -> IngestionSkill:
        """Parse an ingestion SKILL.md file into mapping rules."""
        text = path.read_text(encoding="utf-8")
        post = frontmatter.loads(text)
        meta = dict(post.metadata)

        entity_mappings: list[MappingRule] = []
        for em in meta.get("entity_mappings", []):
            entity_mappings.append(
                MappingRule(
                    source_path=em.get("source_path", ""),
                    target_type="entity",
                    target_label=em.get("target_label", ""),
                    property_map=em.get("property_map", {}),
                )
            )

        relationship_mappings: list[MappingRule] = []
        for rm in meta.get("relationship_mappings", []):
            relationship_mappings.append(
                MappingRule(
                    source_path=rm.get("source_path", ""),
                    target_type="relationship",
                    target_label=rm.get("target_label", ""),
                    property_map=rm.get("property_map", {}),
                )
            )

        skill = IngestionSkill(
            name=meta.get("name", path.stem),
            domain=meta.get("domain", "unknown"),
            version=int(meta.get("version", 1)),
            description=meta.get("description", ""),
            source_format=meta.get("source_format", "json"),
            entity_mappings=entity_mappings,
            relationship_mappings=relationship_mappings,
            body=post.content.strip(),
        )
        logger.info("Loaded ingestion skill: %s (v%d)", skill.name, skill.version)
        return skill

    # ── BaseIngester implementation ───────────────────────────────────────

    async def validate(self, data: Any) -> bool:
        """Check that *data* is a dict or list of dicts."""
        if isinstance(data, dict):
            return True
        if isinstance(data, list) and all(isinstance(item, dict) for item in data):
            return True
        return False

    async def ingest(self, data: Any) -> IngestResult:
        """Map *data* through the skill rules and persist to the graph."""
        records = data if isinstance(data, list) else [data]
        result = IngestResult()

        for record in records:
            # Apply entity mappings.
            for rule in self._skill.entity_mappings:
                try:
                    source_data = self._resolve_path(record, rule.source_path)
                    if source_data is None:
                        continue
                    items = source_data if isinstance(source_data, list) else [source_data]
                    for item in items:
                        props = self._apply_property_map(item, rule.property_map)
                        await self._graph.create_entity(
                            entity_type=rule.target_label,
                            properties=props,
                            source_system=f"skill:{self._skill.name}",
                            source_id=props.get("id", ""),
                            changed_by="skill_based_ingester",
                        )
                        result.entities_created += 1
                except Exception as exc:
                    result.errors.append(f"Entity mapping '{rule.target_label}': {exc}")

            # Apply relationship mappings.
            for rule in self._skill.relationship_mappings:
                try:
                    source_data = self._resolve_path(record, rule.source_path)
                    if source_data is None:
                        continue
                    items = source_data if isinstance(source_data, list) else [source_data]
                    for item in items:
                        props = self._apply_property_map(item, rule.property_map)
                        await self._graph.create_relationship(
                            from_id=props.pop("from_id", ""),
                            to_id=props.pop("to_id", ""),
                            rel_type=rule.target_label,
                            properties=props,
                            changed_by="skill_based_ingester",
                        )
                        result.relationships_created += 1
                except Exception as exc:
                    result.errors.append(f"Relationship mapping '{rule.target_label}': {exc}")

        logger.info(
            "Skill '%s' ingested %d entities, %d relationships (%d errors)",
            self._skill.name,
            result.entities_created,
            result.relationships_created,
            len(result.errors),
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_path(data: dict[str, Any], path: str) -> Any:
        """Walk a dot-separated path into nested dicts/lists.

        Supports simple dot notation (``a.b.c``) and bracket indexing
        (``items[0].name``).
        """
        if not path or path == ".":
            return data

        current: Any = data
        for segment in re.split(r"\.", path):
            if current is None:
                return None
            # Handle bracket indexing like "items[0]".
            match = re.match(r"^(\w+)\[(\d+)]$", segment)
            if match:
                key, idx = match.group(1), int(match.group(2))
                current = current.get(key, []) if isinstance(current, dict) else None
                if isinstance(current, list) and idx < len(current):
                    current = current[idx]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(segment)
            else:
                return None
        return current

    @staticmethod
    def _apply_property_map(
        item: Any, property_map: dict[str, str]
    ) -> dict[str, Any]:
        """Extract properties from *item* using source->target field mapping."""
        if not isinstance(item, dict):
            return {"value": item}

        props: dict[str, Any] = {}
        for target_key, source_key in property_map.items():
            if source_key in item:
                props[target_key] = item[source_key]
        return props
