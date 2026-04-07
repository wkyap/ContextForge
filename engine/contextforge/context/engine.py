"""Context Engine — 6-stage assembly pipeline.

Stages:
  1. Classify query → select retrieval strategy
  2. Retrieve from relevant sources (KG, vector, timeseries)
  3. Prune & deduplicate retrieved chunks
  4. Compose structured context
  5. Compress if over token budget
  6. Cache the assembled context
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from contextforge.context.cache import ContextCache
from contextforge.context.composer import compose_context
from contextforge.context.compressor import compress_context
from contextforge.context.pruner import deduplicate, prune_by_score
from contextforge.context.retrieval_router import (
    RetrievalStrategy,
    classify_query_heuristic,
)
from contextforge.db.neo4j import Neo4jClient
from contextforge.db.qdrant import QdrantClient
from contextforge.db.redis import RedisClient
from contextforge.db.timescale import TimescaleClient
from contextforge.knowledge.embedding_service import EmbeddingService
from contextforge.knowledge.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)


class ContextEngine:
    """Assemble relevant context for a user query."""

    def __init__(
        self,
        neo4j: Neo4jClient,
        qdrant: QdrantClient,
        timescale: TimescaleClient,
        redis: RedisClient,
        embeddings: EmbeddingService,
        *,
        max_context_tokens: int = 6000,
    ) -> None:
        self._graph = TemporalGraph(neo4j)
        self._neo4j = neo4j
        self._qdrant = qdrant
        self._timescale = timescale
        self._embeddings = embeddings
        self._cache = ContextCache(redis)
        self._max_tokens = max_context_tokens

    async def build_context(self, query: str) -> str:
        """Run the 6-stage pipeline and return assembled context."""

        # Stage 0: Check cache
        cached = await self._cache.get(query)
        if cached:
            return cached

        # Stage 1: Classify
        strategy = classify_query_heuristic(query)
        logger.info("Query strategy: %s for: %.80s", strategy.value, query)

        # Stage 2: Retrieve
        kg_entities: list[dict[str, Any]] = []
        kg_relationships: list[dict[str, Any]] = []
        doc_chunks: list[dict[str, Any]] = []
        ts_data: list[dict[str, Any]] = []
        community_summaries: list[dict[str, Any]] = []

        if strategy in (RetrievalStrategy.LOCAL, RetrievalStrategy.HYBRID):
            kg_entities = await self._retrieve_kg_entities(query)
            if kg_entities:
                entity_id = kg_entities[0].get("id", "")
                if entity_id:
                    rels = await self._graph.get_relationships(entity_id)
                    kg_relationships = rels

        if strategy in (RetrievalStrategy.VECTOR, RetrievalStrategy.HYBRID):
            doc_chunks = await self._retrieve_documents(query)

        if strategy == RetrievalStrategy.TIMESERIES:
            ts_data = await self._retrieve_timeseries(query)

        if strategy == RetrievalStrategy.GLOBAL:
            community_summaries = await self._retrieve_communities(query)

        # Stage 3: Prune & deduplicate
        if doc_chunks:
            doc_chunks = prune_by_score(doc_chunks, min_score=0.3, max_chunks=15)
            doc_chunks = deduplicate(doc_chunks, key="text")

        # Stage 4: Compose
        context = compose_context(
            kg_entities=kg_entities,
            kg_relationships=kg_relationships,
            document_chunks=doc_chunks,
            timeseries_data=ts_data,
            community_summaries=community_summaries,
        )

        # Stage 5: Compress
        context = await compress_context(
            context, query, max_tokens=self._max_tokens
        )

        # Stage 6: Cache
        await self._cache.set(query, context)

        return context

    # ── Private retrieval methods ─────────────────────────────────────────

    async def _retrieve_kg_entities(self, query: str) -> list[dict[str, Any]]:
        """Search KG via fulltext index."""
        try:
            results = await self._graph.fulltext_search(query, limit=5)
            return [r["entity"] for r in results]
        except Exception:
            logger.warning("KG fulltext search failed", exc_info=True)
            return []

    async def _retrieve_documents(self, query: str) -> list[dict[str, Any]]:
        """Search document chunks via Qdrant."""
        try:
            vector = await self._embeddings.embed(query)
            results = await self._qdrant.client.query_points(
                collection_name="document_chunks",
                query=vector,
                limit=15,
            )
            return [
                {**pt.payload, "score": pt.score}
                for pt in results.points
            ]
        except Exception:
            logger.warning("Document search failed", exc_info=True)
            return []

    async def _retrieve_timeseries(self, query: str) -> list[dict[str, Any]]:
        """Retrieve recent timeseries data (heuristic entity/param extraction)."""
        # Simplified: search KG for entity, then get its latest parameters
        try:
            entities = await self._retrieve_kg_entities(query)
            if not entities:
                return []
            entity_id = entities[0].get("id", "")
            params = await self._timescale.get_entity_parameters(entity_id)
            if not params:
                return []

            # Get last 24h of the first parameter
            now = datetime.now(UTC)
            start = now - timedelta(hours=24)
            param_name = params[0]["parameter"]
            records = await self._timescale.query_aggregated(
                entity_id, param_name, start=start, end=now, bucket="1 hour"
            )
            return [dict(r) for r in records]
        except Exception:
            logger.warning("Timeseries retrieval failed", exc_info=True)
            return []

    async def _retrieve_communities(self, query: str) -> list[dict[str, Any]]:
        """Search community summaries via Qdrant."""
        try:
            vector = await self._embeddings.embed(query)
            results = await self._qdrant.client.query_points(
                collection_name="community_summaries",
                query=vector,
                limit=5,
            )
            return [
                {**pt.payload, "score": pt.score}
                for pt in results.points
            ]
        except Exception:
            logger.warning("Community search failed", exc_info=True)
            return []
