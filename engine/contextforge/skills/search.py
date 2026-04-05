"""Semantic skill search via Qdrant."""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client.models import PointStruct

from contextforge.db.qdrant import QdrantClient
from contextforge.skills.loader import Skill

logger = logging.getLogger(__name__)

COLLECTION = "skill_catalog"


async def index_skills(
    qdrant: QdrantClient,
    skills: list[Skill],
    embed_fn: Any,
) -> int:
    """Embed and upsert all skills into the skill_catalog collection.

    *embed_fn* should be an async callable: ``async (text: str) -> list[float]``.
    Returns the number of skills indexed.
    """
    points: list[PointStruct] = []
    for i, skill in enumerate(skills):
        vector = await embed_fn(skill.search_text)
        points.append(
            PointStruct(
                id=i,
                vector=vector,
                payload={
                    "skill_name": skill.name,
                    "skill_type": skill.type,
                    "description": skill.description,
                    "domain": skill.domain,
                    "author": skill.author,
                    "version": skill.version,
                    "tags": skill.tags,
                    "active": True,
                },
            )
        )

    if points:
        await qdrant.upsert(COLLECTION, points)
        logger.info("Indexed %d skills into Qdrant", len(points))
    return len(points)


async def search_skills(
    qdrant: QdrantClient,
    query_vector: list[float],
    *,
    limit: int = 5,
    domain: str | None = None,
    skill_type: str | None = None,
) -> list[dict[str, Any]]:
    """Search for relevant skills by embedding similarity."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    conditions = []
    if domain:
        conditions.append(FieldCondition(key="domain", match=MatchValue(value=domain)))
    if skill_type:
        conditions.append(FieldCondition(key="skill_type", match=MatchValue(value=skill_type)))

    filter_ = Filter(must=conditions) if conditions else None

    results = await qdrant.client.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        limit=limit,
        query_filter=filter_,
    )
    return [
        {**point.payload, "score": point.score}
        for point in results.points
    ]
