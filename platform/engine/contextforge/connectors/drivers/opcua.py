"""OPC-UA connector driver — polls a list of node ids on an OPC-UA server.

Uses `asyncua` (lazy-imported so the engine still starts when the package is
not installed). Configuration schema lives in domains/_examples/connector_opcua.md.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from contextforge.connectors.base import ConnectorBase, Record
from contextforge.connectors.registry import get_connector_registry

logger = logging.getLogger(__name__)


class OPCUAConnector(ConnectorBase):
    source_kind = "opcua"

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        super().__init__(name=name, config=config)
        self._client: Any = None  # asyncua.Client when running

    async def connect(self) -> None:
        try:
            from asyncua import Client
        except ImportError as exc:
            raise RuntimeError(
                "asyncua is not installed. Install with `pip install asyncua` "
                "to enable the OPC-UA connector."
            ) from exc

        if "url" not in self.config:
            raise ValueError("opcua connector requires 'url' in config (e.g. opc.tcp://host:4840)")
        if not self.config.get("nodes"):
            raise ValueError("opcua connector requires 'nodes' (list of node ids) in config")

        self._client = Client(url=self.config["url"])
        if (user := self.config.get("username")) and (pw := self.config.get("password")):
            self._client.set_user(user)
            self._client.set_password(pw)
        await self._client.connect()
        logger.info(
            "OPC-UA connector %s connected to %s, polling %d nodes",
            self.name, self.config["url"], len(self.config["nodes"]),
        )

    async def stream(self) -> AsyncIterator[Record]:
        if self._client is None:
            raise RuntimeError("connect() must be called before stream()")
        node_ids: list[str] = list(self.config["nodes"])
        interval: float = float(self.config.get("interval_s", 5))

        while True:
            try:
                for node_id in node_ids:
                    try:
                        node = self._client.get_node(node_id)
                        value = await node.read_value()
                    except Exception as exc:
                        logger.warning("opcua %s read failed for %s: %s", self.name, node_id, exc)
                        yield Record(
                            payload={"error": str(exc), "node": node_id},
                            source=f"opcua://{self.name}/{node_id}",
                            metadata={"status": "error", "node": node_id},
                        )
                        continue
                    yield Record(
                        payload={"entity_id": node_id, "parameter": "value", "value": value},
                        source=f"opcua://{self.name}/{node_id}",
                        metadata={"node": node_id},
                    )
            except asyncio.CancelledError:
                raise
            await asyncio.sleep(interval)

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                logger.exception("Error disconnecting OPC-UA client for %s", self.name)
            self._client = None


get_connector_registry().register(OPCUAConnector)
