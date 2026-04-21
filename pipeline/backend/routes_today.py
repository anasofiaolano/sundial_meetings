"""FastAPI APIRouter for the Today action queue."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from models import (
    get_today_queue,
    complete_followup,
    snooze_followup,
    disqualify_contact,
    create_followup,
    get_contact,
)

DB_PATH = Path(__file__).parent / "pipeline.db"

router = APIRouter(tags=["today"])

CADENCE_DAYS = {"hot": 7, "warm": 30, "cold": 90}


class CompleteRequest(BaseModel):
    outcome: str  # connected, voicemail, no_answer
    notes: Optional[str] = None


class SnoozeRequest(BaseModel):
    days: int = 7


class DisqualifyRequest(BaseModel):
    reason: str


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@router.get("/api/pipeline/today")
def get_today_action_queue():
    try:
        conn = _db()
        items = get_today_queue(conn)
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load today queue: {exc}")

    today = date.today()
    overdue_count = 0
    today_count = 0
    this_week_count = 0
    hot_count = 0
    enriched = []

    for item in items:
        row = dict(item) if not isinstance(item, dict) else item
        due = row.get("due_date", str(today))
        try:
            due_date = date.fromisoformat(due[:10])
        except (ValueError, TypeError):
            due_date = today

        if due_date < today:
            band = "overdue"
            overdue_count += 1
        elif due_date == today:
            band = "today"
            today_count += 1
        elif due_date <= today + timedelta(days=7):
            band = "this_week"
            this_week_count += 1
        else:
            band = "upcoming"

        row["priority_band"] = band
        row["days_overdue"] = max(0, (today - due_date).days)

        if (row.get("temperature") or "").lower() == "hot":
            hot_count += 1

        enriched.append(row)

    return {
        "items": enriched,
        "summary": {
            "total": len(enriched),
            "overdue": overdue_count,
            "today": today_count,
            "this_week": this_week_count,
            "hot_leads": hot_count,
        },
    }


@router.post("/api/pipeline/today/{followup_id}/complete")
def complete_followup_endpoint(followup_id: str, body: CompleteRequest):
    try:
        conn = _db()
        completed = complete_followup(conn, followup_id, body.outcome, body.notes)
        if not completed:
            conn.close()
            raise HTTPException(status_code=404, detail="Followup not found")

        # Auto-create next followup based on contact temperature
        contact_id = completed.get("contact_id")
        contact = get_contact(conn, contact_id) if contact_id else None
        new_followup = None

        if contact:
            temp = (contact.get("temperature") or "warm").lower()
            days = CADENCE_DAYS.get(temp, 30)
            next_due = (date.today() + timedelta(days=days)).isoformat()
            new_followup = create_followup(
                conn, contact_id=contact_id, due_date=next_due,
                reason=f"{days}-day follow-up", action_type="call", status="pending"
            )

        conn.close()
        return {"completed": completed, "next_followup": new_followup}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/pipeline/today/{followup_id}/snooze")
def snooze_followup_endpoint(followup_id: str, body: SnoozeRequest):
    try:
        conn = _db()
        new_date = (date.today() + timedelta(days=body.days)).isoformat()
        result = snooze_followup(conn, followup_id, new_date)
        conn.close()
        if not result:
            raise HTTPException(status_code=404, detail="Followup not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/pipeline/today/{contact_id}/disqualify")
def disqualify_endpoint(contact_id: str, body: DisqualifyRequest):
    try:
        conn = _db()
        disqualify_contact(conn, contact_id, body.reason)
        conn.close()
        return {"ok": True, "contact_id": contact_id, "reason": body.reason}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
