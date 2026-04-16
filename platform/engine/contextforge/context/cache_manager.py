"""Context-as-cache manager — memory flush and warm-up utilities."""

from __future__ import annotations

import logging
from typing import Any

from contextforge.context.cache import ContextCache
from contextforge.db.redis import RedisClient

logger = logging.getLogger(__name__)


class CacheManager:
    """Manage context cache lifecycle — warm-up, flush, stats."""

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._cache = ContextCache(redis)

    @property
    def cache(self) -> ContextCache:
        return self._cache

    async def flush_all(self) -> int:
        """Flush all cached contexts. Returns count of deleted keys."""
        # Scan for all context cache keys
        pattern = "contextforge:context_cache:*"
        count = 0
        async for key in self._redis.client.scan_iter(match=pattern, count=100):
            await self._redis.client.delete(key)
            count += 1
        logger.info("Flushed %d context cache entries", count)
        return count

    async def warm_up(
        self,
        queries: list[str],
        build_context_fn: Any,
    ) -> int:
        """Pre-populate cache for common queries.

        *build_context_fn* should be an async callable:
        ``async (query: str) -> str``.
        """
        warmed = 0
        for query in queries:
            existing = await self._cache.get(query)
            if existing:
                continue
            try:
                context = await build_context_fn(query)
                await self._cache.set(query, context)
                warmed += 1
            except Exception:
                logger.warning("Failed to warm cache for: %.60s", query, exc_info=True)
        logger.info("Warmed %d/%d cache entries", warmed, len(queries))
        return warmed

    async def stats(self) -> dict[str, int]:
        """Get basic cache statistics."""
        pattern = "contextforge:context_cache:*"
        count = 0
        async for _ in self._redis.client.scan_iter(match=pattern, count=100):
            count += 1
        return {"cached_entries": count}
