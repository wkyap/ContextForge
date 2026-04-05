"""Redis async client for caching and pub/sub."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Key prefix for all ContextForge keys.
PREFIX = "contextforge"


class RedisClient:
    """Async Redis wrapper with typed helpers."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: aioredis.Redis | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._client is not None:
            return
        self._client = aioredis.from_url(
            self._url, decode_responses=True, max_connections=20
        )
        await self._client.ping()
        logger.info("Redis connected (%s)", self._url.split("@")[-1])

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis client closed")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("RedisClient not connected — call connect() first")
        return self._client

    # ── Key-value helpers ─────────────────────────────────────────────────────

    def _key(self, key: str) -> str:
        return f"{PREFIX}:{key}"

    async def get(self, key: str) -> str | None:
        return await self.client.get(self._key(key))

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set(
        self, key: str, value: str, *, ttl_seconds: int | None = None
    ) -> None:
        await self.client.set(self._key(key), value, ex=ttl_seconds)

    async def set_json(
        self, key: str, value: Any, *, ttl_seconds: int | None = None
    ) -> None:
        await self.set(key, json.dumps(value, default=str), ttl_seconds=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self.client.delete(self._key(key))

    # ── Pub/Sub ───────────────────────────────────────────────────────────────

    async def publish(self, channel: str, message: Any) -> int:
        payload = json.dumps(message, default=str) if not isinstance(message, str) else message
        return await self.client.publish(self._key(channel), payload)

    # ── Health ────────────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            logger.exception("Redis health check failed")
            return False
