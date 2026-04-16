"""Qdrant async vector-database client."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from contextforge.namespaces import PLATFORM_QDRANT_PREFIX

logger = logging.getLogger(__name__)

# Canonical platform-owned collection names, prefixed per namespaces.py so that
# apps can add their own `app_<name>__*` collections without risk of collision.
DOCUMENT_CHUNKS_COLLECTION = f"{PLATFORM_QDRANT_PREFIX}document_chunks"
ENTITY_EMBEDDINGS_COLLECTION = f"{PLATFORM_QDRANT_PREFIX}entity_embeddings"
COMMUNITY_SUMMARIES_COLLECTION = f"{PLATFORM_QDRANT_PREFIX}community_summaries"
SKILL_CATALOG_COLLECTION = f"{PLATFORM_QDRANT_PREFIX}skill_catalog"

COLLECTIONS: dict[str, str] = {
    DOCUMENT_CHUNKS_COLLECTION: "Document text embeddings for semantic search",
    ENTITY_EMBEDDINGS_COLLECTION: "Knowledge-graph entity embeddings",
    COMMUNITY_SUMMARIES_COLLECTION: "GraphRAG community summary embeddings",
    SKILL_CATALOG_COLLECTION: "Skill description embeddings for discovery",
}


class QdrantClient:
    """Thin wrapper around the async Qdrant client."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: str | None = None,
        *,
        embedding_dim: int = 1536,
    ) -> None:
        self._host = host
        self._port = port
        self._api_key = api_key
        self._dim = embedding_dim
        self._client: AsyncQdrantClient | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = AsyncQdrantClient(
            host=self._host, port=self._port, api_key=self._api_key
        )
        logger.info("Qdrant client connected (%s:%s)", self._host, self._port)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Qdrant client closed")

    @property
    def client(self) -> AsyncQdrantClient:
        if self._client is None:
            raise RuntimeError("QdrantClient not connected — call connect() first")
        return self._client

    # ── Collection bootstrap ──────────────────────────────────────────────────

    async def ensure_collections(self) -> None:
        """Create all canonical collections if they don't already exist."""
        existing = {c.name for c in (await self.client.get_collections()).collections}
        for name in COLLECTIONS:
            if name not in existing:
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=self._dim, distance=Distance.COSINE
                    ),
                )
                logger.info("Created Qdrant collection: %s (dim=%d)", name, self._dim)
            else:
                logger.debug("Qdrant collection already exists: %s", name)

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    async def upsert(
        self,
        collection: str,
        points: list[PointStruct],
    ) -> None:
        await self.client.upsert(collection_name=collection, points=points)

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        limit: int = 10,
        score_threshold: float | None = None,
        filter_: Any | None = None,
    ) -> list[Any]:
        result = await self.client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=filter_,
        )
        return result.points

    async def delete(self, collection: str, ids: list[str | int]) -> None:
        from qdrant_client.http.models import PointIdsList

        await self.client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=list(ids)),
        )

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            collections = await self.client.get_collections()
            return collections is not None
        except Exception:
            logger.exception("Qdrant health check failed")
            return False
