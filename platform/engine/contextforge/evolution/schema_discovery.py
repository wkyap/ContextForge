"""Schema Discovery Agent — discovers new entity types and relationships from data."""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from contextforge.db.neo4j import Neo4jClient

logger = logging.getLogger(__name__)

_DISCOVERY_PROMPT = """Analyze the following entities and relationships in the knowledge graph.
Identify patterns that suggest new entity types or relationship types that are not yet
in the schema.

Current entity types: {entity_types}
Current relationship types: {relationship_types}

Sample entities:
{sample_entities}

Suggest new schema elements as JSON:
{{
  "new_entity_types": [{{"type": "...", "description": "...", "suggested_properties": [...]}}],
  "new_relationship_types": [{{"type": "...", "from": "...", "to": "...", "description": "..."}}],
  "reasoning": "..."
}}"""


class SchemaDiscoveryAgent:
    """Analyze the knowledge graph to discover emergent schema patterns."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def discover(self) -> dict[str, Any]:
        """Analyze current graph state and propose schema additions."""
        # Get current schema
        entity_types = await self._neo4j.execute_cypher(
            "MATCH (e:Entity {_is_current: true}) "
            "RETURN DISTINCT e._type AS type, count(e) AS count "
            "ORDER BY count DESC LIMIT 20"
        )
        rel_types = await self._neo4j.execute_cypher(
            "MATCH ()-[r {_is_current: true}]->() "
            "RETURN DISTINCT type(r) AS type, count(r) AS count "
            "ORDER BY count DESC LIMIT 20"
        )
        sample = await self._neo4j.execute_cypher(
            "MATCH (e:Entity {_is_current: true}) RETURN e {.id, ._type, .name} AS entity LIMIT 30"
        )

        et_str = ", ".join(f"{r['type']} ({r['count']})" for r in entity_types) or "none"
        rt_str = ", ".join(f"{r['type']} ({r['count']})" for r in rel_types) or "none"
        sample_str = json.dumps([r["entity"] for r in sample], indent=2, default=str)

        response = await litellm.acompletion(
            model="openai/gpt-4o",
            messages=[{
                "role": "user",
                "content": _DISCOVERY_PROMPT.format(
                    entity_types=et_str, relationship_types=rt_str, sample_entities=sample_str
                ),
            }],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            result = {
                "new_entity_types": [],
                "new_relationship_types": [],
                "reasoning": "Parse error",
            }

        logger.info(
            "Schema discovery: %d new entity types, %d new relationships proposed",
            len(result.get("new_entity_types", [])),
            len(result.get("new_relationship_types", [])),
        )
        return result
