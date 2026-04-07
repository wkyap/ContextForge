"""WebSocket streaming agent endpoint."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from contextforge.agents.graph import run_agent_chat_streaming

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/agent/chat")
async def agent_chat_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming agent chat.

    Client sends JSON: {"message": "...", "thread_id": "..." (optional), "domain": "..."}
    Server streams JSON events:
      {"type": "node",  "node": "...", "keys": [...], "thread_id": "..."}
      {"type": "done",  "content": "...",            "thread_id": "..."}
      {"type": "error", "content": "...",            "thread_id": "..."}
    """
    await websocket.accept()
    logger.info("WebSocket connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            message = data.get("message", "").strip()
            if not message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            thread_id = data.get("thread_id") or str(uuid.uuid4())
            domain = data.get("domain", "industrial")
            agent = websocket.app.state.agent

            try:
                async for event in run_agent_chat_streaming(
                    agent, message, thread_id=thread_id, domain=domain
                ):
                    if event["type"] == "node":
                        await websocket.send_json({
                            "type": "node",
                            "node": event["node"],
                            "keys": event["keys"],
                            "thread_id": event["thread_id"],
                        })
                    elif event["type"] == "done":
                        await websocket.send_json({
                            "type": "done",
                            "content": event["response"],
                            "thread_id": event["thread_id"],
                        })
                    elif event["type"] == "error":
                        await websocket.send_json({
                            "type": "error",
                            "content": event["error"],
                            "thread_id": event["thread_id"],
                        })
            except Exception as exc:
                logger.exception("Agent error in WebSocket")
                await websocket.send_json({
                    "type": "error",
                    "content": f"Agent error: {exc}",
                    "thread_id": thread_id,
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
