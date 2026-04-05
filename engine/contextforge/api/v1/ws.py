"""WebSocket streaming agent endpoint."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from contextforge.agents.graph import run_agent_chat

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/agent/chat")
async def agent_chat_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming agent chat.

    Client sends JSON: {"message": "...", "thread_id": "..." (optional)}
    Server streams JSON: {"type": "token|done|error", "content": "...", "thread_id": "..."}
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
            agent = websocket.app.state.agent

            try:
                # For now, non-streaming (full response). Streaming will be added
                # when LangGraph's astream is wired up with token callbacks.
                response_text, thread_id = await run_agent_chat(
                    agent, message, thread_id=thread_id
                )
                await websocket.send_json({
                    "type": "done",
                    "content": response_text,
                    "thread_id": thread_id,
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
