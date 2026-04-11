"""Entity resolution — synonym/alias merging for knowledge graph entities."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.qdrant import QdrantClient
from contextforge.knowledge.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class EntityResolver:
    """Detect and merge duplicate entities using name matching and embeddings."""

    def __init__(
        self,
        neo4j: Neo4jClient,
        qdrant: QdrantClient,
        embeddings: EmbeddingService,
        *,
        similarity_threshold: float = 0.92,
    ) -> None:
        self._neo4j = neo4j
        self._qdrant = qdrant
        self._embeddings = embeddings
        self._threshold = similarity_threshold

    async def find_duplicates(
        self, name: str, entity_type: str
    ) -> list[dict[str, Any]]:
        """Find potential duplicate entities by name similarity."""
        # Step 1: exact / fuzzy match in Neo4j fulltext index
        neo4j_matches = await self._neo4j.execute_cypher(
            """
            CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
            YIELD node, score
            WHERE node._is_current = true AND node._type = $entity_type
            RETURN node.id AS id, node.name AS name, score
            ORDER BY score DESC
            LIMIT 10
            """,
            {"query": name, "entity_type": entity_type},
        )

        # Step 2: semantic similarity via Qdrant
        vector = await self._embeddings.embed(f"{entity_type}: {name}")
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        qdrant_results = await self._qdrant.client.query_points(
            collection_name="entity_embeddings",
            query=vector,
            limit=10,
            score_threshold=self._threshold,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="entity_type", match=MatchValue(value=entity_type)
                    )
                ]
            ),
        )

        # Merge candidates
        candidates: dict[str, dict[str, Any]] = {}
        for m in neo4j_matches:
            candidates[m["id"]] = {
                "id": m["id"],
                "name": m["name"],
                "neo4j_score": m["score"],
                "vector_score": 0.0,
            }
        for pt in qdrant_results.points:
            eid = (pt.payload or {}).get("entity_id", "")
            if eid in candidates:
                candidates[eid]["vector_score"] = pt.score
            else:
                candidates[eid] = {
                    "id": eid,
                    "name": (pt.payload or {}).get("entity_name", ""),
                    "neo4j_score": 0.0,
                    "vector_score": pt.score,
                }

        return sorted(candidates.values(), key=lambda c: c["vector_score"], reverse=True)

    async def merge_entities(
        self, keep_id: str, merge_ids: list[str]
    ) -> dict[str, Any]:
        """Merge duplicate entities into the canonical one.

        Moves all relationships from merge_ids to keep_id, then retires the
        duplicate nodes.
        """
        result = await self._neo4j.execute_write(
            """
            UNWIND $merge_ids AS mid
            MATCH (dup:Entity {id: mid, _is_current: true})
            MATCH (keep:Entity {id: $keep_id, _is_current: true})
            // Redirect outgoing relationships
            OPTIONAL MATCH (dup)-[r_out]->(target)
            WHERE r_out._is_current = true
            FOREACH (_ IN CASE WHEN target IS NOT NULL THEN [1] ELSE [] END |
                CREATE (keep)-[nr:RELATES_TO]->(target)
                SET nr = r_out {.*}
                SET r_out._is_current = false
            )
            // Redirect incoming relationships
            WITH dup, keep
            OPTIONAL MATCH (source)-[r_in]->(dup)
            WHERE r_in._is_current = true
            FOREACH (_ IN CASE WHEN source IS NOT NULL THEN [1] ELSE [] END |
                CREATE (source)-[nr:RELATES_TO]->(keep)
                SET nr = r_in {.*}
                SET r_in._is_current = false
            )
            // Retire duplicate
            SET dup._is_current = false, dup._valid_to = datetime()
            RETURN count(dup) AS merged_count
            """,
            {"keep_id": keep_id, "merge_ids": merge_ids},
        )
        merged = result[0]["merged_count"] if result else 0
        logger.info("Merged %d entities into %s", merged, keep_id)
        return {"keep_id": keep_id, "merged_count": merged}
