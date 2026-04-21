"""
FastAPI APIRouter for the pipeline kanban view.

Endpoints:
  GET  /api/pipeline/stages       — contacts grouped by stage with health indicators
  GET  /api/pipeline/summary      — pipeline summary, revenue by stage, health counts
  POST /api/pipeline/contacts/{id}/stage — move a contact to a new stage
"""

import sqlite3
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from models import (
    VALID_STAGES,
    init_db,
    get_contact,
    update_contact,
    create_interaction,
    get_pipeline_summary,
)

DB_PATH = Path(__file__).parent / "pipeline.db"

router = APIRouter(tags=["pipeline"])

FUNNEL_STAGES = {"new_lead", "discovery"}
ACTIVE_STAGES = {"ballpark", "dsa", "design", "materials"}
CLOSING_STAGES = {"contract", "build"}

# Expected days between touches per stage
CADENCE_DAYS = {
    "new_lead": 3, "discovery": 14, "ballpark": 14,
    "dsa": 7, "design": 7, "materials": 7,
    "contract": 14, "build": 14,
}


class StageUpdateRequest(BaseModel):
    stage: str


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _compute_health(stage, last_touch_date):
    if last_touch_date is None:
        return "red"
    try:
        last_dt = datetime.fromisoformat(last_touch_date).date()
    except (ValueError, TypeError):
        return "red"
    days_since = (date.today() - last_dt).days
    cadence = CADENCE_DAYS.get(stage, 14)
    if days_since <= cadence:
        return "green"
    if days_since <= cadence * 1.5:
        return "amber"
    return "red"


@router.get("/api/pipeline/stages")
def get_stages():
    try:
        conn = _get_db()
        rows = conn.execute("""
            SELECT c.*,
                (SELECT i.date FROM interactions i
                 WHERE i.contact_id = c.id ORDER BY i.date DESC LIMIT 1) AS last_touch_date,
                (SELECT i.summary FROM interactions i
                 WHERE i.contact_id = c.id ORDER BY i.date DESC LIMIT 1) AS last_touch_summary
            FROM contacts c ORDER BY c.stage, c.name
        """).fetchall()
        conn.close()

        funnel, active, closing, nurture = [], [], [], []

        for row in rows:
            d = dict(row)
            d["health"] = _compute_health(d["stage"], d.get("last_touch_date"))

            # Days since last touch
            lt = d.get("last_touch_date")
            if lt:
                try:
                    days = (date.today() - datetime.fromisoformat(lt).date()).days
                    if days >= 90:
                        nurture.append(d)
                        continue
                except (ValueError, TypeError):
                    pass

            stage = d["stage"]
            if stage in FUNNEL_STAGES:
                funnel.append(d)
            elif stage in ACTIVE_STAGES:
                active.append(d)
            elif stage in CLOSING_STAGES:
                closing.append(d)
            else:
                funnel.append(d)

        return {
            "funnel": {"stages": ["new_lead", "discovery"], "count": len(funnel), "contacts": funnel},
            "active": {"stages": ["ballpark", "dsa", "design", "materials"], "count": len(active), "contacts": active},
            "closing": {"stages": ["contract", "build"], "count": len(closing), "contacts": closing},
            "nurture": {"count": len(nurture), "contacts": nurture},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/pipeline/summary")
def get_summary():
    try:
        conn = _get_db()
        summary = get_pipeline_summary(conn)

        rev_rows = conn.execute(
            "SELECT stage, COALESCE(SUM(estimated_value), 0) AS total FROM contacts GROUP BY stage"
        ).fetchall()
        revenue = {r["stage"]: r["total"] for r in rev_rows}

        rows = conn.execute("""
            SELECT c.stage,
                (SELECT i.date FROM interactions i
                 WHERE i.contact_id = c.id ORDER BY i.date DESC LIMIT 1) AS last_touch_date
            FROM contacts c
        """).fetchall()
        conn.close()

        health = {"green": 0, "amber": 0, "red": 0}
        for r in rows:
            health[_compute_health(r["stage"], r["last_touch_date"])] += 1

        return {**summary, "revenue_by_stage": revenue, "health_counts": health}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/pipeline/contacts/{contact_id}/stage")
def update_stage(contact_id: str, body: StageUpdateRequest):
    if body.stage not in VALID_STAGES:
        raise HTTPException(status_code=422, detail=f"Invalid stage: {body.stage}")
    try:
        conn = _get_db()
        contact = get_contact(conn, contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        old_stage = contact["stage"]
        update_contact(conn, contact_id, stage=body.stage)
        create_interaction(conn, contact_id=contact_id, type="stage_change",
                          date=date.today().isoformat(),
                          summary=f"Stage changed from {old_stage} to {body.stage}")
        conn.close()
        return {"id": contact_id, "old_stage": old_stage, "new_stage": body.stage}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
