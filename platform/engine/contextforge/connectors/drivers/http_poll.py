"""HTTP polling connector — periodically GET a URL and emit the response.

Useful for REST APIs that don't support webhooks/streaming, including FHIR
resource endpoints, weather APIs, vendor health endpoints, etc. Supports basic
auth, bearer token, and arbitrary headers via config.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from contextforge.connectors.base import ConnectorBase, Record
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


class HTTPPollConnector(ConnectorBase):
    source_kind = "http_poll"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if "url" not in self.config:
            raise ValueError("http_poll connector requires 'url' in config")
        headers: dict[str, str] = dict(self.config.get("headers", {}))
        if token := self.config.get("bearer_token"):
            headers["Authorization"] = f"Bearer {token}"
        auth: tuple[str, str] | None = None
        if (user := self.config.get("username")) and (pw := self.config.get("password")):
            auth = (user, pw)
        timeout = float(self.config.get("timeout_s", 30))
        self._client = httpx.AsyncClient(headers=headers, auth=auth, timeout=timeout)
        logger.info(
            "HTTP poll connector %s ready (url=%s, interval=%ss)",
            self.name, self.config["url"], self.config.get("interval_s", 60),
        )

    async def stream(self) -> AsyncIterator[Record]:
        if self._client is None:
            raise RuntimeError("connect() must be called before stream()")
        url: str = self.config["url"]
        interval: float = float(self.config.get("interval_s", 60))
        method: str = str(self.config.get("method", "GET")).upper()
        params: dict[str, Any] = dict(self.config.get("params", {}))

        while True:
            try:
                response = await self._client.request(method, url, params=params)
                response.raise_for_status()
                try:
                    body: Any = response.json()
                except ValueError:
                    body = {"raw": response.text}
                # Wrap non-dict bodies (e.g. JSON arrays) so the sink contract holds.
                if not isinstance(body, dict):
                    body = {"items": body}
                yield Record(
                    payload=body,
                    source=f"http://{self.name}",
                    metadata={"url": url, "status": response.status_code},
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("http_poll %s request failed: %s", self.name, exc)
                yield Record(
                    payload={"error": str(exc)},
                    source=f"http://{self.name}",
                    metadata={"url": url, "status": "error"},
                )
            await asyncio.sleep(interval)

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                logger.exception("Error closing HTTP client for %s", self.name)
            self._client = None


get_connector_registry().register(HTTPPollConnector)
