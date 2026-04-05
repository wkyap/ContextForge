"""Reports API — dashboard metrics, at-risk detection, SSG compliance reports."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from contextforge.api.deps import PostgresDep

router = APIRouter(prefix="/reports")


@router.get("/dashboard")
async def dashboard_metrics(
    postgres: PostgresDep,
    programme_id: str | None = None,
) -> dict:
    """Real-time programme KPI metrics for coordinator dashboard."""
    where = ""
    params: list = []
    if programme_id:
        where = "WHERE programme_id::text = $1"
        params = [programme_id]

    # Trainee counts by status
    status_rows = await postgres.fetch(
        f"SELECT status, count(*) as cnt FROM trainees {where} GROUP BY status",
        params,
    )
    status_counts = {r["status"]: r["cnt"] for r in status_rows}

    # Total trainees
    total = sum(status_counts.values())
    placed = status_counts.get("placed", 0)
    completed = status_counts.get("completed", 0) + placed
    placement_rate = (placed / completed * 100) if completed > 0 else 0

    # Pending verifications
    pending_docs = await postgres.fetch_one(
        "SELECT count(*) as cnt FROM documents WHERE verification_status = 'pending'",
        [],
    )

    # Pending enrolment reviews
    pending_apps = await postgres.fetch_one(
        "SELECT count(*) as cnt FROM applications WHERE status = 'pending'",
        [],
    )

    return {
        "kpi": {
            "total_trainees": total,
            "placement_rate": round(placement_rate, 1),
            "pending_verifications": pending_docs["cnt"] if pending_docs else 0,
            "pending_enrolments": pending_apps["cnt"] if pending_apps else 0,
        },
        "trainee_status": status_counts,
        "active_trainees": status_counts.get("training", 0),
        "completed": completed,
        "placed": placed,
    }


@router.get("/at-risk")
async def at_risk_trainees(postgres: PostgresDep) -> dict:
    """Identify trainees at risk of non-completion or non-placement."""
    # Trainees completed >3 months ago without placement
    rows = await postgres.fetch(
        """SELECT t.id, t.trainee_code, t.name, t.programme_type, t.status,
           t.updated_at, t.email
           FROM trainees t
           WHERE t.status = 'completed'
           AND t.updated_at < now() - interval '90 days'
           AND NOT EXISTS (
               SELECT 1 FROM placements p
               WHERE p.trainee_id = t.id AND p.status = 'verified'
           )
           ORDER BY t.updated_at ASC LIMIT 50""",
        [],
    )

    at_risk = []
    for r in rows:
        at_risk.append({
            **dict(r),
            "risk_reason": "Completed training >90 days ago without verified placement",
            "recommended_action": "Send placement reminder; review matching opportunities",
        })

    return {"at_risk_count": len(at_risk), "trainees": at_risk}


@router.get("/placement-funnel")
async def placement_funnel(postgres: PostgresDep) -> dict:
    """Placement pipeline funnel data."""
    status_rows = await postgres.fetch(
        "SELECT status, count(*) as cnt FROM trainees GROUP BY status ORDER BY status",
        [],
    )

    funnel_order = ["applied", "enrolled", "training", "completed", "placed"]
    funnel = {}
    for status in funnel_order:
        funnel[status] = 0
    for r in status_rows:
        if r["status"] in funnel:
            funnel[r["status"]] = r["cnt"]

    return {"funnel": funnel}


@router.post("/ssg")
async def generate_ssg_report(
    postgres: PostgresDep,
    programme_id: str | None = None,
) -> JSONResponse:
    """Generate SSG compliance report data.

    Full Excel generation will be implemented in Sprint 4.
    For now, returns the structured data that would go into the report.
    """
    # Programme summary
    programmes = await postgres.fetch(
        "SELECT * FROM programmes WHERE active = true", []
    )

    # Aggregate metrics
    metrics = await postgres.fetch(
        """SELECT p.name as programme_name, p.type as programme_type,
           count(DISTINCT t.id) as total_trainees,
           count(DISTINCT CASE WHEN t.status = 'completed' THEN t.id END) as completed,
           count(DISTINCT CASE WHEN t.status = 'placed' THEN t.id END) as placed,
           count(DISTINCT pl.id) as verified_placements
           FROM programmes p
           LEFT JOIN trainees t ON t.programme_id = p.id
           LEFT JOIN placements pl ON pl.trainee_id = t.id AND pl.status = 'verified'
           GROUP BY p.id, p.name, p.type""",
        [],
    )

    return JSONResponse(
        content={
            "report_type": "ssg_monthly",
            "requires_signoff": True,
            "programmes": [dict(p) for p in programmes],
            "metrics": [dict(m) for m in metrics],
            "note": "Excel export will be available in Sprint 4",
        }
    )
