"""MCP tool server — Structured SQL query operations."""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class SqlTools:
    """Tool definitions for parameterized SQL queries against PostgreSQL, exposed to agents."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_query",
                    "description": (
                        "Execute a parameterized read-only SQL query against PostgreSQL. "
                        "Uses $1, $2 style placeholders for parameters."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "SQL query with $1, $2, ... placeholders",
                            },
                            "params": {
                                "type": "array",
                                "items": {},
                                "default": [],
                                "description": "Ordered list of parameter values",
                            },
                            "limit": {
                                "type": "integer",
                                "default": 100,
                                "description": "Maximum number of rows to return",
                            },
                        },
                        "required": ["sql"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_table_schema",
                    "description": "Get column names, types, and constraints for a specific table",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "Fully qualified table name (schema.table or just table)",
                            },
                        },
                        "required": ["table_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tables",
                    "description": "List all tables in the database, optionally filtered by schema",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "schema_name": {
                                "type": "string",
                                "default": "public",
                                "description": "Schema to list tables from",
                            },
                        },
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, args: dict[str, Any]) -> Any:
        if tool_name == "execute_query":
            return await self._execute_query(args)
        elif tool_name == "get_table_schema":
            return await self._get_table_schema(args)
        elif tool_name == "list_tables":
            return await self._list_tables(args)
        raise ValueError(f"Unknown tool: {tool_name}")

    async def _execute_query(self, args: dict[str, Any]) -> dict[str, Any]:
        sql: str = args["sql"]
        params: list[Any] = args.get("params", [])
        limit: int = args.get("limit", 100)

        # Enforce read-only by wrapping in a read-only transaction
        async with self._pool.acquire() as conn:
            async with conn.transaction(readonly=True):
                stmt = await conn.prepare(sql)
                records = await stmt.fetch(*params, timeout=30)

        rows = [dict(r) for r in records[:limit]]
        logger.info("execute_query returned %d rows (limit=%d)", len(rows), limit)
        return {"rows": rows, "row_count": len(rows), "truncated": len(records) > limit}

    async def _get_table_schema(self, args: dict[str, Any]) -> dict[str, Any]:
        table_name: str = args["table_name"]

        # Split schema.table if provided
        if "." in table_name:
            schema, table = table_name.split(".", 1)
        else:
            schema, table = "public", table_name

        query = """
            SELECT column_name, data_type, is_nullable, column_default,
                   character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """

        async with self._pool.acquire() as conn:
            records = await conn.fetch(query, schema, table)

        columns = [dict(r) for r in records]
        logger.info("get_table_schema: %s.%s has %d columns", schema, table, len(columns))
        return {"schema": schema, "table": table, "columns": columns}

    async def _list_tables(self, args: dict[str, Any]) -> dict[str, Any]:
        schema_name: str = args.get("schema_name", "public")

        query = """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
        """

        async with self._pool.acquire() as conn:
            records = await conn.fetch(query, schema_name)

        tables = [dict(r) for r in records]
        logger.info("list_tables: schema=%s found %d tables", schema_name, len(tables))
        return {"schema": schema_name, "tables": tables}
