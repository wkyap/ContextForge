"""Memory manager — LangGraph Store wrapper for cross-session agent memory."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from contextforge.db.redis import RedisClient

logger = logging.getLogger(__name__)


class MemoryManager:
    """Cross-session memory stored in Redis, keyed by user + namespace."""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    def _key(self, user_id: str, namespace: str) -> str:
        return f"memory:{user_id}:{namespace}"

    async def store(
        self, user_id: str, namespace: str, key: str, value: Any
    ) -> None:
        """Store a memory entry."""
        mem_key = self._key(user_id, namespace)
        existing = await self._redis.get_json(mem_key) or {}
        existing[key] = {
            "value": value,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        await self._redis.set_json(mem_key, existing)
        logger.debug("Memory stored: %s/%s/%s", user_id, namespace, key)

    async def recall(
        self, user_id: str, namespace: str, key: str | None = None
    ) -> Any:
        """Recall a memory entry, or all entries in a namespace."""
        mem_key = self._key(user_id, namespace)
        data = await self._redis.get_json(mem_key)
        if data is None:
            return None
        if key:
            entry = data.get(key)
            return entry["value"] if entry else None
        return {k: v["value"] for k, v in data.items()}

    async def forget(
        self, user_id: str, namespace: str, key: str | None = None
    ) -> None:
        """Remove a specific memory or clear a namespace."""
        if key is None:
            await self._redis.delete(self._key(user_id, namespace))
            logger.debug("Memory cleared: %s/%s", user_id, namespace)
        else:
            mem_key = self._key(user_id, namespace)
            data = await self._redis.get_json(mem_key) or {}
            data.pop(key, None)
            await self._redis.set_json(mem_key, data)
            logger.debug("Memory forgotten: %s/%s/%s", user_id, namespace, key)

    async def list_namespaces(self, user_id: str) -> list[str]:
        """List all memory namespaces for a user."""
        pattern = f"contextforge:memory:{user_id}:*"
        namespaces = []
        async for key in self._redis.client.scan_iter(match=pattern, count=100):
            # key format: contextforge:memory:user_id:namespace
            ns = str(key).split(":")[-1]
            namespaces.append(ns)
        return namespaces
