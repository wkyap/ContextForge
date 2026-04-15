"""Governance API — proposal review, autonomy levels, audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep, RedisDep
from contextforge.governance.approval_queue import ApprovalQueue
from contextforge.governance.audit_trail import AuditTrail
from contextforge.governance.autonomy_controller import LEVELS, AutonomyController

router = APIRouter(prefix="/governance")


# ── Models ───────────────────────────────────────────────────────────────────

class ProposalCreate(BaseModel):
    proposal_type: str = Field(..., max_length=50)
    title: str = Field(..., max_length=200)
    description: str = ""
    proposed_by: str = Field(default="system")
    content: dict[str, Any] = {}
    autonomy_level: int = 0
    confidence_score: float = 0.0


class ProposalReview(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected|modified)$")
    approver_id: str
    reason: str = ""


class AutonomyPromotion(BaseModel):
    promoted_by: str


# ── Proposals ────────────────────────────────────────────────────────────────

@router.get("/proposals")
async def list_proposals(
    postgres: PostgresDep,
    redis: RedisDep,
    status: str = Query("pending", pattern="^(pending|approved|rejected|modified|all)$"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    queue = ApprovalQueue(postgres, redis)
    if status == "all":
        rows = await postgres.fetch(
            """
            SELECT id, type, title, description, proposed_by, status,
                   confidence_score, created_at, reviewed_at, approver_id
            FROM proposals
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        proposals = [dict(r) for r in rows]
    else:
        if status == "pending":
            proposals = await queue.list_pending(limit=limit)
        else:
            rows = await postgres.fetch(
                """
                SELECT id, type, title, description, proposed_by, status,
                       confidence_score, created_at, reviewed_at, approver_id
                FROM proposals
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                status, limit,
            )
            proposals = [dict(r) for r in rows]
    return {"count": len(proposals), "proposals": proposals}


@router.post("/proposals")
async def create_proposal(
    body: ProposalCreate,
    postgres: PostgresDep,
    redis: RedisDep,
) -> dict[str, Any]:
    queue = ApprovalQueue(postgres, redis)
    proposal_id = await queue.submit_proposal(
        proposal_type=body.proposal_type,
        title=body.title,
        description=body.description,
        proposed_by=body.proposed_by,
        content=body.content,
        autonomy_level=body.autonomy_level,
        confidence_score=body.confidence_score,
    )
    return {"id": proposal_id, "status": "pending"}


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, postgres: PostgresDep) -> dict[str, Any]:
    row = await postgres.fetchrow(
        "SELECT * FROM proposals WHERE id = $1", proposal_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return dict(row)


@router.post("/proposals/{proposal_id}/review")
async def review_proposal(
    proposal_id: str,
    body: ProposalReview,
    postgres: PostgresDep,
    redis: RedisDep,
) -> dict[str, Any]:
    queue = ApprovalQueue(postgres, redis)
    updated = await queue.review_proposal(
        proposal_id,
        status=body.status,
        approver_id=body.approver_id,
        reason=body.reason,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Proposal not found or already reviewed")
    return {"id": proposal_id, "status": body.status}


# ── Autonomy Levels ─────────────────────────────────────────────────────────

@router.get("/autonomy-levels")
async def list_autonomy_levels(postgres: PostgresDep) -> dict[str, Any]:
    rows = await postgres.fetch(
        """
        SELECT function_name, autonomy_level, proposal_count,
               approval_count, approval_rate, promoted_at, promoted_by
        FROM autonomy_levels
        ORDER BY function_name
        """
    )
    return {
        "level_definitions": LEVELS,
        "functions": [dict(r) for r in rows],
    }


@router.get("/autonomy-levels/{function_name}")
async def get_autonomy_level(
    function_name: str,
    postgres: PostgresDep,
    redis: RedisDep,
) -> dict[str, Any]:
    controller = AutonomyController(postgres, redis)
    level = await controller.get_level(function_name)
    can_promote = await controller.check_promotion(function_name)
    return {
        **level,
        "can_promote": can_promote,
        "level_description": LEVELS.get(level.get("autonomy_level", 0), ""),
    }


@router.post("/autonomy-levels/{function_name}/promote")
async def promote_autonomy(
    function_name: str,
    body: AutonomyPromotion,
    postgres: PostgresDep,
    redis: RedisDep,
) -> dict[str, Any]:
    controller = AutonomyController(postgres, redis)
    can_promote = await controller.check_promotion(function_name)
    if not can_promote:
        raise HTTPException(status_code=400, detail="Function does not meet promotion thresholds")
    result = await controller.promote(function_name, promoted_by=body.promoted_by)
    return result


# ── Audit Trail ──────────────────────────────────────────────────────────────

@router.get("/audit")
async def query_audit(
    postgres: PostgresDep,
    user_id: str | None = Query(None),
    action_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    since: str | None = Query(None, description="ISO 8601 datetime"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    trail = AuditTrail(postgres)
    since_dt = datetime.fromisoformat(since) if since else None
    entries = await trail.query(
        user_id=user_id,
        action_type=action_type,
        resource_type=resource_type,
        since=since_dt,
        limit=limit,
    )
    return {"count": len(entries), "entries": entries}
