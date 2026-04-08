"""Search API — unified semantic search across knowledge graph, documents, and skills."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from contextforge.api.deps import Neo4jDep, QdrantDep, SettingsDep
from contextforge.knowledge.embedding_service import EmbeddingService
from contextforge.knowledge.temporal_graph import TemporalGraph
from contextforge.skills.search import search_skills

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    sources: list[str] = Field(
        default=["documents", "entities", "skills"],
        description="Which sources to search: documents, entities, skills",
    )
    limit: int = Field(default=10, ge=1, le=100)
    domain: str | None = None


@router.post("")
async def semantic_search(
    body: SearchRequest,
    neo4j: Neo4jDep,
    qdrant: QdrantDep,
    settings: SettingsDep,
    request: Request,
) -> dict[str, Any]:
    embeddings = EmbeddingService(settings)
    query_vector = await embeddings.embed(body.query)
    results: dict[str, list[dict[str, Any]]] = {}

    # Search documents
    if "documents" in body.sources:
        try:
            doc_results = await qdrant.search(
                "document_chunks",
                query_vector,
                limit=body.limit,
            )
            results["documents"] = [
                {**pt.payload, "score": pt.score} for pt in doc_results
            ]
        except Exception:
            results["documents"] = []

    # Search entities via graph fulltext
    if "entities" in body.sources:
        try:
            graph = TemporalGraph(neo4j)
            entity_results = await graph.fulltext_search(body.query, limit=body.limit)
            results["entities"] = entity_results
        except Exception:
            results["entities"] = []

    # Search skills
    if "skills" in body.sources:
        try:
            skill_results = await search_skills(
                qdrant,
                query_vector,
                limit=body.limit,
                domain=body.domain,
            )
            results["skills"] = skill_results
        except Exception:
            results["skills"] = []

    total = sum(len(v) for v in results.values())
    return {"query": body.query, "total_results": total, "results": results}


@router.get("")
async def quick_search(
    neo4j: Neo4jDep,
    qdrant: QdrantDep,
    settings: SettingsDep,
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    """GET-based quick search across entities and documents."""
    embeddings = EmbeddingService(settings)
    query_vector = await embeddings.embed(q)
    results: list[dict[str, Any]] = []

    # Entity fulltext search
    try:
        graph = TemporalGraph(neo4j)
        entities = await graph.fulltext_search(q, limit=limit)
        for e in entities:
            results.append({"type": "entity", **e})
    except Exception:
        logger.warning("Entity fulltext search failed for q=%r", q, exc_info=True)

    # Document vector search
    try:
        docs = await qdrant.search("document_chunks", query_vector, limit=limit)
        for pt in docs:
            results.append({"type": "document", **pt.payload, "score": pt.score})
    except Exception:
        logger.warning("Document vector search failed for q=%r", q, exc_info=True)

    # Sort by score descending
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return {"query": q, "count": len(results), "results": results[:limit]}
