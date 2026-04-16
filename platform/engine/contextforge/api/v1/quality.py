"""Quality Studio API — evaluate agent responses and track improvements."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/quality")


# ── Models ──────────────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    thread_id: str = ""
    query: str = Field(..., min_length=1)
    response: str = Field(..., min_length=1)
    context_snippet: str = ""


class ProposalUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(approved|rejected|applied)$")


# ── Evaluations ─────────────────────────────────────────────────────────────

@router.get("/evaluations")
async def list_evaluations(
    postgres: PostgresDep,
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List quality evaluations, optionally filtered by score range."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if min_score is not None:
        conditions.append(f"overall_score >= ${idx}")
        params.append(min_score)
        idx += 1
    if max_score is not None:
        conditions.append(f"overall_score <= ${idx}")
        params.append(max_score)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await postgres.fetch(
        f"SELECT * FROM quality_evaluations {where} ORDER BY evaluated_at DESC "
        f"LIMIT ${idx} OFFSET ${idx + 1}",
        *params, limit, offset,
    )
    total = await postgres.fetchval(
        f"SELECT COUNT(*) FROM quality_evaluations {where}", *params
    )
    return {"total": total or 0, "evaluations": [dict(r) for r in rows]}


@router.post("/evaluate", status_code=201)
async def evaluate_response(body: EvaluateRequest, postgres: PostgresDep) -> dict[str, Any]:
    """Run quality evaluation on a query/response pair and persist the result."""
    import json

    from contextforge.evolution.quality_improvement import QualityImprover

    improver = QualityImprover()
    result = await improver.evaluate_response(
        query=body.query,
        response=body.response,
        context=body.context_snippet,
    )

    eval_id = str(uuid.uuid4())
    scores = result.get("scores", {})
    overall = float(result.get("overall", 0))
    issues = result.get("issues", [])
    suggestions = result.get("suggestions", [])

    await postgres.execute(
        """INSERT INTO quality_evaluations
           (id, thread_id, query, response, context_snippet, scores,
            overall_score, issues, suggestions)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
        [
            eval_id, body.thread_id, body.query, body.response,
            body.context_snippet, json.dumps(scores), overall,
            json.dumps(issues), json.dumps(suggestions),
        ],
    )

    return {
        "id": eval_id,
        "scores": scores,
        "overall": overall,
        "issues": issues,
        "suggestions": suggestions,
    }


@router.get("/metrics")
async def quality_metrics(postgres: PostgresDep) -> dict[str, Any]:
    """Aggregate quality metrics for the dashboard."""
    total = await postgres.fetchval("SELECT COUNT(*) FROM quality_evaluations") or 0
    avg_score = await postgres.fetchval(
        "SELECT ROUND(AVG(overall_score)::numeric, 2) FROM quality_evaluations"
    )

    dimension_rows = await postgres.fetch(
        """SELECT
             ROUND(AVG((scores->>'relevance')::numeric), 2) AS avg_relevance,
             ROUND(AVG((scores->>'accuracy')::numeric), 2) AS avg_accuracy,
             ROUND(AVG((scores->>'completeness')::numeric), 2) AS avg_completeness,
             ROUND(AVG((scores->>'conciseness')::numeric), 2) AS avg_conciseness,
             ROUND(AVG((scores->>'safety')::numeric), 2) AS avg_safety
           FROM quality_evaluations
           WHERE scores != '{}'::jsonb""",
    )
    dimensions = dict(dimension_rows[0]) if dimension_rows else {}

    # Score distribution buckets
    dist_rows = await postgres.fetch(
        """SELECT
             CASE
               WHEN overall_score >= 4.5 THEN 'excellent'
               WHEN overall_score >= 3.5 THEN 'good'
               WHEN overall_score >= 2.5 THEN 'fair'
               ELSE 'poor'
             END AS bucket,
             COUNT(*) AS count
           FROM quality_evaluations
           GROUP BY bucket
           ORDER BY bucket""",
    )
    distribution = {r["bucket"]: r["count"] for r in dist_rows}

    # Recent trend (last 7 days, daily average)
    trend_rows = await postgres.fetch(
        """SELECT DATE(evaluated_at) AS day,
                  ROUND(AVG(overall_score)::numeric, 2) AS avg_score,
                  COUNT(*) AS count
           FROM quality_evaluations
           WHERE evaluated_at >= now() - interval '7 days'
           GROUP BY day ORDER BY day""",
    )
    trend = [{"day": str(r["day"]), "avg_score": float(r["avg_score"]), "count": r["count"]}
             for r in trend_rows]

    return {
        "total_evaluations": total,
        "average_score": float(avg_score) if avg_score else 0,
        "dimensions": dimensions,
        "distribution": distribution,
        "trend": trend,
    }


# ── Improvement proposals ───────────────────────────────────────────────────

@router.get("/proposals")
async def list_proposals(
    postgres: PostgresDep,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List improvement proposals."""
    conditions: list[str] = []
    params: list[Any] = []
    idx = 1

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await postgres.fetch(
        f"SELECT * FROM improvement_proposals {where} ORDER BY created_at DESC "
        f"LIMIT ${idx} OFFSET ${idx + 1}",
        *params, limit, offset,
    )
    total = await postgres.fetchval(
        f"SELECT COUNT(*) FROM improvement_proposals {where}", *params
    )
    return {"total": total or 0, "proposals": [dict(r) for r in rows]}


@router.post("/proposals/generate", status_code=201)
async def generate_proposal(postgres: PostgresDep, limit: int = 20) -> dict[str, Any]:
    """Generate an improvement proposal from recent low-scoring evaluations."""
    import json

    from contextforge.evolution.quality_improvement import QualityImprover

    rows = await postgres.fetch(
        """SELECT scores, overall_score, query, response, issues, suggestions
           FROM quality_evaluations
           ORDER BY overall_score ASC, evaluated_at DESC
           LIMIT $1""",
        limit,
    )
    if not rows:
        raise HTTPException(404, "No evaluations to analyze")

    evaluations = [dict(r) for r in rows]
    improver = QualityImprover()
    proposal = await improver.generate_improvement_proposal(evaluations)

    proposal_id = str(uuid.uuid4())
    await postgres.execute(
        """INSERT INTO improvement_proposals
           (id, proposal_type, title, description, changes, expected_impact)
           VALUES ($1,$2,$3,$4,$5,$6)""",
        [
            proposal_id,
            proposal.get("proposal_type", "unknown"),
            proposal.get("title", "Untitled"),
            proposal.get("description", ""),
            json.dumps(proposal.get("changes", [])),
            proposal.get("expected_impact", ""),
        ],
    )

    return {"id": proposal_id, **proposal}


@router.patch("/proposals/{proposal_id}")
async def update_proposal(
    proposal_id: str, body: ProposalUpdate, postgres: PostgresDep
) -> dict[str, Any]:
    """Approve, reject, or mark a proposal as applied."""
    await postgres.execute(
        "UPDATE improvement_proposals SET status = $1 WHERE id::text = $2",
        [body.status, proposal_id],
    )
    return {"updated": True, "status": body.status}
