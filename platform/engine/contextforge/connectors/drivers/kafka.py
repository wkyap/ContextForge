"""Kafka connector driver — consumes a topic and emits each message as a Record.

Uses `aiokafka` (lazy-imported so the engine still starts when the package is
not installed). Configuration schema lives in domains/_examples/connector_kafka.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from contextforge.connectors.base import ConnectorBase, Record
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


class KafkaConnector(ConnectorBase):
    source_kind = "kafka"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self._consumer: Any = None  # aiokafka.AIOKafkaConsumer when running

    async def connect(self) -> None:
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as exc:
            raise RuntimeError(
                "aiokafka is not installed. Install with `pip install aiokafka` "
                "to enable the Kafka connector."
            ) from exc

        topics = self.config.get("topics") or (
            [self.config["topic"]] if "topic" in self.config else None
        )
        if not topics:
            raise ValueError("kafka connector requires 'topic' or 'topics' in config")
        bootstrap = self.config.get("bootstrap_servers", "localhost:9092")
        group_id = self.config.get("group_id", f"contextforge-{self.name}")

        kwargs: dict[str, Any] = {
            "bootstrap_servers": bootstrap,
            "group_id": group_id,
            "auto_offset_reset": self.config.get("auto_offset_reset", "latest"),
            "enable_auto_commit": bool(self.config.get("enable_auto_commit", True)),
        }
        if (sasl_user := self.config.get("sasl_username")) and (
            sasl_pw := self.config.get("sasl_password")
        ):
            kwargs.update(
                security_protocol=self.config.get("security_protocol", "SASL_PLAINTEXT"),
                sasl_mechanism=self.config.get("sasl_mechanism", "PLAIN"),
                sasl_plain_username=sasl_user,
                sasl_plain_password=sasl_pw,
            )

        self._consumer = AIOKafkaConsumer(*topics, **kwargs)
        await self._consumer.start()
        logger.info(
            "Kafka connector %s subscribed to %s on %s (group=%s)",
            self.name, topics, bootstrap, group_id,
        )

    async def stream(self) -> AsyncIterator[Record]:
        if self._consumer is None:
            raise RuntimeError("connect() must be called before stream()")
        async for message in self._consumer:
            try:
                payload: Any = json.loads(message.value)
                if not isinstance(payload, dict):
                    payload = {"value": payload}
            except (ValueError, TypeError):
                payload = {"raw": (message.value or b"").decode("utf-8", errors="replace")}
            yield Record(
                payload=payload,
                source=f"kafka://{self.name}/{message.topic}",
                metadata={
                    "topic": message.topic,
                    "partition": message.partition,
                    "offset": message.offset,
                },
            )

    async def close(self) -> None:
        if self._consumer is not None:
            try:
                await self._consumer.stop()
            except Exception:
                logger.exception("Error stopping Kafka consumer for %s", self.name)
            self._consumer = None


get_connector_registry().register(KafkaConnector)
