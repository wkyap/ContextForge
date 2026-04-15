"""Community detection — Leiden clustering on the knowledge graph."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.db.neo4j import Neo4jClient

logger = logging.getLogger(__name__)


class CommunityDetector:
    """Run Leiden community detection on current Entity nodes.

    Requires the Neo4j Graph Data Science (GDS) plugin.
    """

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def detect_communities(
        self, *, resolution: float = 1.0, min_community_size: int = 2
    ) -> dict[str, Any]:
        """Project a graph, run Leiden, write community IDs back to nodes."""

        # Step 1: Create in-memory graph projection
        await self._neo4j.execute_cypher(
            """
            CALL gds.graph.project(
                'entity_graph',
                {Entity: {properties: ['_is_current']}},
                {RELATES_TO: {orientation: 'UNDIRECTED'}}
            )
            """
        )

        # Step 2: Run Leiden clustering
        result = await self._neo4j.execute_cypher(
            """
            CALL gds.leiden.write('entity_graph', {
                writeProperty: '_community_id',
                resolution: $resolution,
                minCommunitySize: $min_size
            })
            YIELD communityCount, modularity, ranLevels
            RETURN communityCount, modularity, ranLevels
            """,
            {"resolution": resolution, "min_size": min_community_size},
        )

        # Step 3: Drop projection
        await self._neo4j.execute_cypher(
            "CALL gds.graph.drop('entity_graph', false)"
        )

        stats = result[0] if result else {}
        logger.info(
            "Leiden clustering: %d communities, modularity=%.4f",
            stats.get("communityCount", 0),
            stats.get("modularity", 0),
        )
        return stats

    async def get_community_members(
        self, community_id: str, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get all current entities in a given community."""
        result = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {_community_id: $cid, _is_current: true})
            RETURN e {.*} AS entity
            ORDER BY e._updated_at DESC
            LIMIT $limit
            """,
            {"cid": community_id, "limit": limit},
        )
        return [r["entity"] for r in result]

    async def list_communities(self) -> list[dict[str, Any]]:
        """List all communities with member counts."""
        result = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {_is_current: true})
            WHERE e._community_id IS NOT NULL
            RETURN e._community_id AS community_id, count(e) AS member_count
            ORDER BY member_count DESC
            """
        )
        return result
