"""Graph API — entity CRUD, relationships, and time-travel queries on the knowledge graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from contextforge.api.deps import Neo4jDep
from contextforge.knowledge.temporal_graph import TemporalGraph

router = APIRouter(prefix="/graph")


# ── Models ───────────────────────────────────────────────────────────────────

class EntityCreate(BaseModel):
    entity_type: str = Field(..., max_length=100)
    properties: dict[str, Any]
    source_system: str = "api"
    source_id: str = ""
    confidence: float = 1.0


class EntityUpdate(BaseModel):
    properties: dict[str, Any]
    changed_by: str = "api"
    change_reason: str = ""


class RelationshipCreate(BaseModel):
    from_id: str
    to_id: str
    rel_type: str = Field(..., max_length=100)
    properties: dict[str, Any] | None = None
    confidence: float = 1.0


# ── Entities ─────────────────────────────────────────────────────────────────

@router.get("/entities")
async def list_entities(
    neo4j: Neo4jDep,
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    entities = await graph.find_entities(entity_type, limit=limit)
    return {"count": len(entities), "entities": entities}


@router.post("/entities")
async def create_entity(body: EntityCreate, neo4j: Neo4jDep) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    entity = await graph.create_entity(
        entity_type=body.entity_type,
        properties=body.properties,
        source_system=body.source_system,
        source_id=body.source_id,
        confidence=body.confidence,
    )
    return entity


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    neo4j: Neo4jDep,
    at: str | None = Query(None, description="ISO 8601 datetime for time-travel"),
) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    if at:
        entity = await graph.get_entity_at(entity_id, at)
    else:
        entity = await graph.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/entities/{entity_id}")
async def update_entity(
    entity_id: str,
    body: EntityUpdate,
    neo4j: Neo4jDep,
) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    entity = await graph.update_entity(
        entity_id,
        properties=body.properties,
        changed_by=body.changed_by,
        change_reason=body.change_reason,
    )
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities/{entity_id}/history")
async def get_entity_history(entity_id: str, neo4j: Neo4jDep) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    versions = await graph.get_entity_history(entity_id)
    return {"entity_id": entity_id, "version_count": len(versions), "versions": versions}


# ── Relationships ────────────────────────────────────────────────────────────

@router.get("/entities/{entity_id}/relationships")
async def get_relationships(
    entity_id: str,
    neo4j: Neo4jDep,
    direction: str = Query("both", pattern="^(in|out|both)$"),
) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    rels = await graph.get_relationships(entity_id, direction=direction)
    return {"entity_id": entity_id, "count": len(rels), "relationships": rels}


@router.post("/relationships")
async def create_relationship(body: RelationshipCreate, neo4j: Neo4jDep) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    rel = await graph.create_relationship(
        body.from_id,
        body.to_id,
        body.rel_type,
        properties=body.properties,
        confidence=body.confidence,
    )
    if not rel:
        raise HTTPException(status_code=404, detail="One or both entities not found")
    return rel


# ── Search ───────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_graph(
    neo4j: Neo4jDep,
    q: str = Query(..., min_length=1, description="Fulltext search query"),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    graph = TemporalGraph(neo4j)
    results = await graph.fulltext_search(q, limit=limit)
    return {"count": len(results), "results": results}
