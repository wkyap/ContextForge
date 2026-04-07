"""MCP tool server — TimeSeries operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from contextforge.db.timescale import TimescaleClient


class TimeseriesTools:
    """Tool definitions for timeseries queries, exposed to agents."""

    def __init__(self, timescale: TimescaleClient) -> None:
        self._ts = timescale

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_latest_reading",
                    "description": "Get the most recent telemetry reading for an entity parameter",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                            "parameter": {"type": "string", "description": "e.g., heart_rate, temperature, vibration"},
                        },
                        "required": ["entity_id", "parameter"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trend",
                    "description": "Get aggregated trend data for an entity parameter over a time range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                            "parameter": {"type": "string"},
                            "hours_back": {"type": "integer", "default": 24},
                            "bucket": {"type": "string", "default": "1 hour"},
                        },
                        "required": ["entity_id", "parameter"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_entity_parameters",
                    "description": "List all telemetry parameters recorded for an entity",
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
        if tool_name == "get_latest_reading":
            rec = await self._ts.query_latest(args["entity_id"], args["parameter"])
            return dict(rec) if rec else None
        elif tool_name == "get_trend":
            now = datetime.now(UTC)
            start = now - timedelta(hours=args.get("hours_back", 24))
            records = await self._ts.query_aggregated(
                args["entity_id"], args["parameter"],
                start=start, end=now, bucket=args.get("bucket", "1 hour"),
            )
            return [dict(r) for r in records]
        elif tool_name == "list_entity_parameters":
            records = await self._ts.get_entity_parameters(args["entity_id"])
            return [dict(r) for r in records]
        raise ValueError(f"Unknown tool: {tool_name}")
