"""WebSocket streaming agent endpoint."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from contextforge.agents.graph import run_agent_chat_streaming
from contextforge.tenancy.budget import TenantBudgetController
from contextforge.tenancy.context import DEFAULT_TENANT, TenantContext

logger = logging.getLogger(__name__)

router = APIRouter()


async def _resolve_ws_tenant(websocket: WebSocket) -> TenantContext:
    """Resolve the tenant for a WebSocket connection.

    WebSocket handshakes do not run the standard ``TenantMiddleware`` (it's
    only wired for HTTP), so we read the same ``X-Tenant-ID`` header (or fall
    back to the default tenant) to keep the cost-accounting path consistent
    with the REST endpoints.
    """
    header_val = websocket.headers.get("x-tenant-id")
    if not header_val:
        return DEFAULT_TENANT
    try:
        postgres = websocket.app.state.postgres
        row = await postgres.fetch_one(
            """SELECT id::text, slug, name, plan, settings
               FROM tenants
               WHERE id::text = $1 OR slug = $1""",
            header_val,
        )
        if row is None:
            return DEFAULT_TENANT
        return TenantContext(
            tenant_id=row["id"],
            slug=row["slug"],
            name=row["name"],
            plan=row["plan"],
            settings=row.get("settings") or {},
        )
    except Exception:
        logger.exception("WebSocket tenant lookup failed; falling back to default")
        return DEFAULT_TENANT


@router.websocket("/ws/agent/chat")
async def agent_chat_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming agent chat.

    Client sends JSON: {"message": "...", "thread_id": "..." (optional), "domain": "..."}
    Server streams JSON events:
      {"type": "node",  "node": "...", "keys": [...], "thread_id": "..."}
      {"type": "done",  "content": "...", "usage": {...}, "thread_id": "..."}
      {"type": "error", "content": "...",                  "thread_id": "..."}
    """
    await websocket.accept()
    logger.info("WebSocket connected")

    tenant = await _resolve_ws_tenant(websocket)
    try:
        controller: TenantBudgetController | None = TenantBudgetController(
            websocket.app.state.postgres
        )
    except Exception:
        controller = None

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

            # Pre-flight budget gate
            if controller is not None:
                try:
                    if not await controller.check_budget(tenant.tenant_id):
                        await websocket.send_json({
                            "type": "error",
                            "content": "Tenant budget exceeded for the current period",
                            "thread_id": thread_id,
                        })
                        continue
                except Exception:
                    logger.exception("Budget pre-check failed; allowing request")

            try:
                async for event in run_agent_chat_streaming(
                    agent,
                    message,
                    thread_id=thread_id,
                    domain=domain,
                    user_id=tenant.tenant_id,
                ):
                    if event["type"] == "node":
                        await websocket.send_json({
                            "type": "node",
                            "node": event["node"],
                            "keys": event["keys"],
                            "thread_id": event["thread_id"],
                        })
                    elif event["type"] == "done":
                        usage = event.get("usage") or {"tokens": 0, "cost_usd": 0.0}
                        await websocket.send_json({
                            "type": "done",
                            "content": event["response"],
                            "thread_id": event["thread_id"],
                            "usage": usage,
                        })
                        if controller is not None:
                            try:
                                await controller.record_usage(
                                    tenant.tenant_id,
                                    tokens=int(usage.get("tokens", 0)),
                                    cost_usd=float(usage.get("cost_usd", 0.0)),
                                    user_id=tenant.tenant_id,
                                    operation="agent_chat_ws",
                                )
                            except Exception:
                                logger.exception("Failed to record WS usage")
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
