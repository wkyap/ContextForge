"""Redis-backed context cache."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from contextforge.db.redis import RedisClient

logger = logging.getLogger(__name__)

DEFAULT_TTL = 300  # 5 minutes


def _cache_key(query: str) -> str:
    """Deterministic cache key from query text."""
    h = hashlib.sha256(query.encode()).hexdigest()[:16]
    return f"context_cache:{h}"


class ContextCache:
    """Cache assembled context to avoid redundant retrieval."""

    def __init__(self, redis: RedisClient, *, ttl: int = DEFAULT_TTL) -> None:
        self._redis = redis
        self._ttl = ttl

    async def get(self, query: str) -> str | None:
        """Return cached context if available."""
        result = await self._redis.get(_cache_key(query))
        if result:
            logger.debug("Context cache HIT for query: %.60s", query)
        return result

    async def set(self, query: str, context: str) -> None:
        """Cache assembled context."""
        await self._redis.set(_cache_key(query), context, ttl_seconds=self._ttl)
        logger.debug("Context cached (ttl=%ds) for query: %.60s", self._ttl, query)

    async def invalidate(self, query: str) -> None:
        """Remove a specific cached context."""
        await self._redis.delete(_cache_key(query))

    async def get_metadata(self, query: str) -> dict[str, Any] | None:
        """Get cache metadata (strategy, sources, timestamps)."""
        return await self._redis.get_json(f"{_cache_key(query)}:meta")

    async def set_metadata(self, query: str, metadata: dict[str, Any]) -> None:
        """Store cache metadata alongside the context."""
        await self._redis.set_json(
            f"{_cache_key(query)}:meta", metadata, ttl_seconds=self._ttl
        )
