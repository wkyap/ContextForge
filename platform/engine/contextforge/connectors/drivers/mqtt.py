"""MQTT connector driver — subscribes to topics and emits each message as a Record.

Uses `aiomqtt` (lazy-imported so the engine still starts when the package is
not installed). Configuration schema lives in domains/_examples/connector_mqtt.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from contextforge.connectors.base import ConnectorBase, Record
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


class MQTTConnector(ConnectorBase):
    source_kind = "mqtt"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self._client: Any = None  # aiomqtt.Client when running

    async def connect(self) -> None:
        try:
            import aiomqtt
        except ImportError as exc:
            raise RuntimeError(
                "aiomqtt is not installed. Install with `pip install aiomqtt` "
                "or include the engine 'connectors' extra."
            ) from exc

        host = self.config.get("host", "localhost")
        port = int(self.config.get("port", 1883))
        username = self.config.get("username")
        password = self.config.get("password")

        self._client = aiomqtt.Client(
            hostname=host,
            port=port,
            username=username,
            password=password,
        )
        await self._client.__aenter__()
        topics = self.config.get("topics", ["#"])
        for t in topics:
            await self._client.subscribe(t)
        logger.info("MQTT connector %s connected to %s:%s topics=%s", self.name, host, port, topics)

    async def stream(self) -> AsyncIterator[Record]:
        if self._client is None:
            raise RuntimeError("connect() must be called before stream()")
        async for message in self._client.messages:
            payload_raw = message.payload
            try:
                payload: Any = json.loads(payload_raw)
                if not isinstance(payload, dict):
                    payload = {"value": payload}
            except (ValueError, TypeError):
                payload = {"raw": payload_raw.decode("utf-8", errors="replace")}
            yield Record(
                payload=payload,
                source=f"mqtt://{self.name}/{message.topic}",
                metadata={"topic": str(message.topic)},
            )

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                logger.exception("Error closing MQTT client for %s", self.name)
            self._client = None


# Self-register on import.
get_connector_registry().register(MQTTConnector)
