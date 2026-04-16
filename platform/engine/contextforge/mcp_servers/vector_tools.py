"""MCP tool server — Vector search operations."""

from __future__ import annotations

from typing import Any

from contextforge.db.qdrant import (
    DOCUMENT_CHUNKS_COLLECTION,
    ENTITY_EMBEDDINGS_COLLECTION,
    QdrantClient,
)
from contextforge.knowledge.embedding_service import EmbeddingService


class VectorTools:
    """Tool definitions for semantic search, exposed to agents."""

    def __init__(self, qdrant: QdrantClient, embeddings: EmbeddingService) -> None:
        self._qdrant = qdrant
        self._embeddings = embeddings

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_documents",
                    "description": "Semantic search over ingested documents",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_similar_entities",
                    "description": "Find entities similar to a given description",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "limit": {"type": "integer", "default": 5},
                        },
                        "required": ["description"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "search_documents":
            vector = await self._embeddings.embed(args["query"])
            results = await self._qdrant.client.query_points(
                collection_name=DOCUMENT_CHUNKS_COLLECTION,
                query=vector,
                limit=args.get("limit", 5),
            )
            return [
                {**(pt.payload or {}), "score": pt.score}
                for pt in results.points
            ]
        elif tool_name == "find_similar_entities":
            vector = await self._embeddings.embed(args["description"])
            results = await self._qdrant.client.query_points(
                collection_name=ENTITY_EMBEDDINGS_COLLECTION,
                query=vector,
                limit=args.get("limit", 5),
            )
            return [
                {**(pt.payload or {}), "score": pt.score}
                for pt in results.points
            ]
        raise ValueError(f"Unknown tool: {tool_name}")
