"""Temporal Knowledge Graph — CRUD with bi-temporal versioning on Neo4j."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from contextforge.db.neo4j import Neo4jClient
from contextforge.namespaces import app_neo4j_entity_label

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class TemporalGraph:
    """High-level API for temporal entity CRUD on Neo4j."""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    # ── Create ────────────────────────────────────────────────────────────

    async def create_entity(
        self,
        *,
        entity_type: str,
        properties: dict[str, Any],
        source_system: str = "manual",
        source_id: str = "",
        confidence: float = 1.0,
        changed_by: str = "manual",
        app: str | None = None,
    ) -> dict[str, Any]:
        """Create a new entity node with temporal metadata.

        ``app`` marks node ownership per the platform/app split (see
        docs/platform-vs-domain.md). ``None`` → platform; pass an app name
        (e.g. ``"careerforge"``) for app-owned entities. The value is stored
        both as a property (``_app``) and as an extra label
        (``:Platform_Entity`` / ``:Cf_Entity``) for Cypher pattern matching.
        """
        entity_id = properties.get("id") or _new_id()
        now = _now()

        props = {
            **properties,
            "id": entity_id,
            "_type": entity_type,
            "_created_at": now,
            "_updated_at": now,
            "_version": 1,
            "_is_current": True,
            "_valid_from": now,
            "_valid_to": None,
            "_changed_by": changed_by,
            "_change_reason": "initial creation",
            "_source_system": source_system,
            "_source_id": source_id,
            "_confidence": confidence,
            "_community_id": None,
            "_app": app,
        }

        # Labels come from a controlled allow-list in namespaces.py; safe to
        # interpolate directly into the Cypher literal.
        ownership_label = app_neo4j_entity_label(app)
        cypher = (
            f"CREATE (e:Entity:`{ownership_label}` $props) "
            "RETURN e {.*} AS entity"
        )
        result = await self._neo4j.execute_write(cypher, {"props": props})
        return result[0]["entity"] if result else props

    # ── Read ──────────────────────────────────────────────────────────────

    async def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Get the current version of an entity."""
        result = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {id: $id, _is_current: true})
            RETURN e {.*} AS entity
            """,
            {"id": entity_id},
        )
        return result[0]["entity"] if result else None

    async def get_entity_at(
        self, entity_id: str, point_in_time: str
    ) -> dict[str, Any] | None:
        """Get the entity as it was at a specific point in time (time-travel)."""
        result = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {id: $id})
            WHERE e._valid_from <= $pit
              AND (e._valid_to IS NULL OR e._valid_to > $pit)
            RETURN e {.*} AS entity
            """,
            {"id": entity_id, "pit": point_in_time},
        )
        return result[0]["entity"] if result else None

    async def get_entity_history(self, entity_id: str) -> list[dict[str, Any]]:
        """Get all versions of an entity, ordered by version."""
        result = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {id: $id})
            RETURN e {.*} AS entity
            ORDER BY e._version
            """,
            {"id": entity_id},
        )
        return [r["entity"] for r in result]

    async def find_entities(
        self,
        entity_type: str | None = None,
        *,
        limit: int = 50,
        current_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Find entities by type."""
        clauses = ["MATCH (e:Entity)"]
        params: dict[str, Any] = {"limit": limit}
        wheres = []

        if current_only:
            wheres.append("e._is_current = true")
        if entity_type:
            wheres.append("e._type = $entity_type")
            params["entity_type"] = entity_type

        if wheres:
            clauses.append("WHERE " + " AND ".join(wheres))
        clauses.append("RETURN e {.*} AS entity ORDER BY e._updated_at DESC LIMIT $limit")

        result = await self._neo4j.execute_cypher("\n".join(clauses), params)
        return [r["entity"] for r in result]

    # ── Update (creates new version) ──────────────────────────────────────

    async def update_entity(
        self,
        entity_id: str,
        *,
        properties: dict[str, Any],
        changed_by: str = "manual",
        change_reason: str = "",
    ) -> dict[str, Any] | None:
        """Create a new version of an entity, retiring the current one.

        The new version inherits the old node's ownership label
        (``Platform_Entity`` / ``Cf_Entity``). We look it up from the old
        node's ``_app`` property — pre-read rather than APOC so the runtime
        stays dependency-free.
        """
        now = _now()

        probe = await self._neo4j.execute_cypher(
            "MATCH (old:Entity {id: $id, _is_current: true}) RETURN old._app AS app",
            {"id": entity_id},
        )
        if not probe:
            return None
        ownership_label = app_neo4j_entity_label(probe[0].get("app"))

        cypher = f"""
            MATCH (old:Entity {{id: $id, _is_current: true}})
            SET old._is_current = false, old._valid_to = $now, old._updated_at = $now
            WITH old
            CREATE (new:Entity:`{ownership_label}`)
            SET new = old {{.*, _is_current: true, _valid_from: $now, _valid_to: null,
                          _version: old._version + 1, _updated_at: $now,
                          _changed_by: $changed_by, _change_reason: $reason}}
            SET new += $props
            RETURN new {{.*}} AS entity
            """
        result = await self._neo4j.execute_write(
            cypher,
            {
                "id": entity_id,
                "now": now,
                "props": properties,
                "changed_by": changed_by,
                "reason": change_reason,
            },
        )
        return result[0]["entity"] if result else None

    # ── Relationships ─────────────────────────────────────────────────────

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        *,
        properties: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> dict[str, Any] | None:
        """Create a temporal relationship between two current entities."""
        now = _now()
        rel_props = {
            **(properties or {}),
            "_created_at": now,
            "_updated_at": now,
            "_is_current": True,
            "_valid_from": now,
            "_valid_to": None,
            "_confidence": confidence,
        }

        result = await self._neo4j.execute_write(
            f"""
            MATCH (a:Entity {{id: $from_id, _is_current: true}})
            MATCH (b:Entity {{id: $to_id, _is_current: true}})
            CREATE (a)-[r:`{rel_type}` $props]->(b)
            RETURN type(r) AS type, r {{.*}} AS rel
            """,
            {"from_id": from_id, "to_id": to_id, "props": rel_props},
        )
        return result[0] if result else None

    async def get_relationships(
        self, entity_id: str, *, direction: str = "both"
    ) -> list[dict[str, Any]]:
        """Get all current relationships for an entity."""
        if direction == "out":
            pattern = "(a)-[r]->(b)"
        elif direction == "in":
            pattern = "(a)<-[r]-(b)"
        else:
            pattern = "(a)-[r]-(b)"

        result = await self._neo4j.execute_cypher(
            f"""
            MATCH {pattern}
            WHERE a.id = $id AND a._is_current = true AND r._is_current = true
            RETURN type(r) AS type, r {{.*}} AS rel, b.id AS target_id, b._type AS target_type
            """,
            {"id": entity_id},
        )
        return result

    # ── Fulltext search ───────────────────────────────────────────────────

    async def fulltext_search(
        self, query: str, *, limit: int = 10, tenant_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Search entities using the full-text index.

        If ``tenant_id`` is supplied, results are restricted to entities
        owned by that tenant or to legacy entities with no ``_tenant_id``
        property (so existing single-tenant data stays visible to every
        tenant). Pass ``None`` to disable scoping.
        """
        if tenant_id is None:
            cypher = """
            CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
            YIELD node, score
            WHERE node._is_current = true
            RETURN node {.*} AS entity, score
            ORDER BY score DESC
            LIMIT $limit
            """
            params: dict[str, Any] = {"query": query, "limit": limit}
        else:
            cypher = """
            CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
            YIELD node, score
            WHERE node._is_current = true
              AND (node._tenant_id = $tenant_id OR node._tenant_id IS NULL)
            RETURN node {.*} AS entity, score
            ORDER BY score DESC
            LIMIT $limit
            """
            params = {"query": query, "limit": limit, "tenant_id": tenant_id}

        result = await self._neo4j.execute_cypher(cypher, params)
        return result
