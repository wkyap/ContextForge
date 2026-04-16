"""MCP tool server — Knowledge Graph operations."""

from __future__ import annotations

from typing import Any

from contextforge.knowledge.temporal_graph import TemporalGraph


class GraphTools:
    """Tool definitions for knowledge graph operations, exposed to agents."""

    def __init__(self, graph: TemporalGraph) -> None:
        self._graph = graph

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_entities",
                    "description": "Search the knowledge graph for entities by name or keyword",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "limit": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity",
                    "description": "Get a specific entity by ID with all properties",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                        },
                        "required": ["entity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity_relationships",
                    "description": "Get all relationships for an entity",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                            "direction": {
                                "type": "string",
                                "enum": ["in", "out", "both"],
                                "default": "both",
                            },
                        },
                        "required": ["entity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity_history",
                    "description": "Get all historical versions of an entity (time-travel)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                        },
                        "required": ["entity_id"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "search_entities":
            return await self._graph.fulltext_search(args["query"], limit=args.get("limit", 5))
        elif tool_name == "get_entity":
            return await self._graph.get_entity(args["entity_id"])
        elif tool_name == "get_entity_relationships":
            return await self._graph.get_relationships(
                args["entity_id"], direction=args.get("direction", "both")
            )
        elif tool_name == "get_entity_history":
            return await self._graph.get_entity_history(args["entity_id"])
        raise ValueError(f"Unknown tool: {tool_name}")
