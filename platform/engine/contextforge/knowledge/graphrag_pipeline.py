"""GraphRAG pipeline — orchestrates extraction, embedding, clustering, and summarisation."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client.models import PointStruct

from contextforge.db.neo4j import Neo4jClient
from contextforge.db.qdrant import QdrantClient
from contextforge.knowledge.community_detection import CommunityDetector
from contextforge.knowledge.embedding_service import EmbeddingService
from contextforge.knowledge.entity_resolution import EntityResolver
from contextforge.knowledge.schema_free_extractor import SchemaFreeExtractor
from contextforge.knowledge.temporal_graph import TemporalGraph

logger = logging.getLogger(__name__)


class GraphRAGPipeline:
    """End-to-end GraphRAG pipeline: ingest text → KG + vectors + communities."""

    def __init__(
        self,
        neo4j: Neo4jClient,
        qdrant: QdrantClient,
        embeddings: EmbeddingService,
    ) -> None:
        self._neo4j = neo4j
        self._qdrant = qdrant
        self._embeddings = embeddings
        self._graph = TemporalGraph(neo4j)
        self._extractor = SchemaFreeExtractor()
        self._resolver = EntityResolver(neo4j, qdrant, embeddings)
        self._communities = CommunityDetector(neo4j)

    # ── Full pipeline ─────────────────────────────────────────────────────

    async def run(
        self,
        documents: list[dict[str, Any]],
        *,
        schema_free_sample_rate: float = 0.1,
    ) -> dict[str, Any]:
        """Run the full GraphRAG pipeline on a batch of documents.

        Each document should have at least: ``{"id": str, "text": str}``.
        Optional: ``source``, ``doc_type``, ``domain``.
        """
        stats: dict[str, int] = {
            "documents": len(documents),
            "chunks_embedded": 0,
            "entities_created": 0,
            "relationships_created": 0,
            "communities_detected": 0,
        }

        # Step 1: Embed and index document chunks
        stats["chunks_embedded"] = await self._embed_documents(documents)

        # Step 2: Extract entities (schema-free on a sample)
        texts = [d["text"] for d in documents]
        extractions = await self._extractor.extract_batch(
            texts, sample_rate=schema_free_sample_rate
        )

        # Step 3: Create entities and relationships in the temporal KG
        for extraction in extractions:
            for ent in extraction.get("entities", []):
                await self._graph.create_entity(
                    entity_type=ent.get("type", "Unknown"),
                    properties={"name": ent.get("name", ""), **ent.get("properties", {})},
                    source_system="graphrag",
                    confidence=ent.get("confidence", 0.5),
                    changed_by="graphrag_pipeline",
                )
                stats["entities_created"] += 1

            for rel in extraction.get("relationships", []):
                # Resolve entities by name (simplified — full impl would use entity IDs)
                await self._neo4j.execute_write(
                    """
                    MATCH (a:Entity {_is_current: true})
                    WHERE a.name = $from_name
                    WITH a LIMIT 1
                    MATCH (b:Entity {_is_current: true})
                    WHERE b.name = $to_name
                    WITH a, b LIMIT 1
                    CREATE (a)-[r:RELATES_TO {
                        _type: $rel_type,
                        _created_at: datetime(),
                        _is_current: true,
                        _valid_from: datetime(),
                        _confidence: $confidence
                    }]->(b)
                    RETURN type(r) AS type
                    """,
                    {
                        "from_name": rel.get("from", ""),
                        "to_name": rel.get("to", ""),
                        "rel_type": rel.get("type", "RELATES_TO"),
                        "confidence": rel.get("confidence", 0.5),
                    },
                )
                stats["relationships_created"] += 1

        # Step 4: Embed entities into Qdrant
        await self._embed_entities()

        # Step 5: Run community detection
        try:
            community_stats = await self._communities.detect_communities()
            stats["communities_detected"] = community_stats.get("communityCount", 0)

            # Step 6: Generate and embed community summaries
            await self._embed_community_summaries()
        except Exception:
            logger.warning("Community detection skipped (GDS plugin may not be available)")

        logger.info("GraphRAG pipeline complete: %s", stats)
        return stats

    # ── Sub-steps ─────────────────────────────────────────────────────────

    async def _embed_documents(self, documents: list[dict[str, Any]]) -> int:
        """Embed document chunks and store in Qdrant."""
        if not documents:
            return 0

        texts = [d["text"] for d in documents]
        vectors = await self._embeddings.embed_batch(texts)

        points = [
            PointStruct(
                id=i,
                vector=vec,
                payload={
                    "document_id": doc.get("id", str(i)),
                    "text": doc["text"][:1000],
                    "source": doc.get("source", "unknown"),
                    "domain": doc.get("domain", ""),
                    "doc_type": doc.get("doc_type", ""),
                },
            )
            for i, (doc, vec) in enumerate(zip(documents, vectors))
        ]
        await self._qdrant.upsert("document_chunks", points)
        return len(points)

    async def _embed_entities(self) -> None:
        """Embed all current entities into Qdrant."""
        entities = await self._neo4j.execute_cypher(
            """
            MATCH (e:Entity {_is_current: true})
            WHERE e.name IS NOT NULL
            RETURN e.id AS id, e.name AS name, e._type AS type, e._community_id AS community_id
            LIMIT 1000
            """
        )
        if not entities:
            return

        texts = [f"{e['type']}: {e['name']}" for e in entities]
        vectors = await self._embeddings.embed_batch(texts)

        points = [
            PointStruct(
                id=i,
                vector=vec,
                payload={
                    "entity_id": ent["id"],
                    "entity_type": ent["type"],
                    "entity_name": ent["name"],
                    "community_id": ent.get("community_id", ""),
                },
            )
            for i, (ent, vec) in enumerate(zip(entities, vectors))
        ]
        await self._qdrant.upsert("entity_embeddings", points)
        logger.info("Embedded %d entities into Qdrant", len(points))

    async def _embed_community_summaries(self) -> None:
        """Generate and embed community summaries."""
        communities = await self._communities.list_communities()
        if not communities:
            return

        import litellm

        points: list[PointStruct] = []
        for i, comm in enumerate(communities[:50]):  # Cap at 50 communities
            members = await self._communities.get_community_members(
                comm["community_id"], limit=20
            )
            if not members:
                continue

            member_names = [m.get("name", m.get("id", "")) for m in members]
            member_types = list({m.get("_type", "") for m in members})

            prompt = (
                f"Summarize this community of {len(members)} entities.\n"
                f"Types: {', '.join(member_types)}\n"
                f"Members: {', '.join(member_names[:20])}\n"
                "Write a 2-3 sentence summary of what connects these entities."
            )
            response = await litellm.acompletion(
                model="openai/gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            summary = response.choices[0].message.content or ""

            vector = await self._embeddings.embed(summary)
            points.append(
                PointStruct(
                    id=i,
                    vector=vector,
                    payload={
                        "community_id": comm["community_id"],
                        "summary_text": summary,
                        "member_count": comm["member_count"],
                        "keywords": member_types,
                    },
                )
            )

        if points:
            await self._qdrant.upsert("community_summaries", points)
            logger.info("Embedded %d community summaries", len(points))
