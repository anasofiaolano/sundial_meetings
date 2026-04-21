"""FastAPI APIRouter for contact CRUD and detail view."""

import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from models import (
    create_followup,
    create_interaction,
    create_contact,
    get_contact,
    list_contacts,
    list_interactions,
    update_contact,
)

DB_PATH = Path(__file__).parent / "pipeline.db"

router = APIRouter(tags=["contacts"])


def _db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Request schemas ──────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    location: Optional[str] = None
    stage: str = "new_lead"
    temperature: str = "warm"
    budget_range: Optional[str] = None
    sqft: Optional[str] = None
    style: Optional[str] = None
    lot_status: Optional[str] = None
    rapport_notes: Optional[str] = None
    estimated_value: Optional[float] = None


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    stage: Optional[str] = None
    temperature: Optional[str] = None
    budget_range: Optional[str] = None
    sqft: Optional[str] = None
    style: Optional[str] = None
    lot_status: Optional[str] = None
    rapport_notes: Optional[str] = None
    estimated_value: Optional[float] = None


class InteractionCreate(BaseModel):
    type: str = "call"
    summary: str = ""
    questions_detected: Optional[list] = None
    action_items: Optional[list] = None


class RapportUpdate(BaseModel):
    rapport_notes: str


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/api/pipeline/contacts")
def list_contacts_endpoint(stage: Optional[str] = None, temperature: Optional[str] = None, search: Optional[str] = None):
    try:
        conn = _db()
        contacts = list_contacts(conn, stage=stage, temperature=temperature)
        conn.close()
        if search:
            search_lower = search.lower()
            contacts = [c for c in contacts if search_lower in (c.get("name") or "").lower()]
        return contacts
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/pipeline/contacts/{contact_id}")
def get_contact_detail(contact_id: str):
    try:
        conn = _db()
        contact = get_contact(conn, contact_id)
        if not contact:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")

        interactions = list_interactions(conn, contact_id)

        # Get pending followups
        followups = conn.execute(
            "SELECT * FROM followups WHERE contact_id = ? AND status = 'pending' ORDER BY due_date",
            (contact_id,)
        ).fetchall()
        followups = [dict(f) for f in followups]
        conn.close()

        next_touch = followups[0] if followups else None

        # Stats
        total_interactions = len(interactions)
        first_date = interactions[-1]["date"] if interactions else None
        last_date = interactions[0]["date"] if interactions else None
        days_since_first = 0
        days_since_last = 0
        if first_date:
            try:
                days_since_first = (date.today() - datetime.fromisoformat(first_date).date()).days
            except (ValueError, TypeError):
                pass
        if last_date:
            try:
                days_since_last = (date.today() - datetime.fromisoformat(last_date).date()).days
            except (ValueError, TypeError):
                pass

        return {
            **contact,
            "interactions": interactions,
            "followups": followups,
            "next_touch": next_touch,
            "stats": {
                "total_interactions": total_interactions,
                "days_since_first_touch": days_since_first,
                "days_since_last_touch": days_since_last,
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/pipeline/contacts", status_code=201)
def create_contact_endpoint(body: ContactCreate):
    try:
        conn = _db()
        contact = create_contact(conn, **body.model_dump(exclude_none=True))

        # Auto-create first followup 7 days out
        due_date = (date.today() + timedelta(days=7)).isoformat()
        create_followup(conn, contact_id=contact["id"], due_date=due_date,
                        reason="Initial follow-up", action_type="call", status="pending")
        conn.close()
        return contact
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/api/pipeline/contacts/{contact_id}")
def update_contact_endpoint(contact_id: str, body: ContactUpdate):
    try:
        conn = _db()
        existing = get_contact(conn, contact_id)
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if updates:
            result = update_contact(conn, contact_id, **updates)
        else:
            result = existing
        conn.close()
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/pipeline/contacts/{contact_id}/interactions", status_code=201)
def add_interaction_endpoint(contact_id: str, body: InteractionCreate):
    try:
        conn = _db()
        existing = get_contact(conn, contact_id)
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")

        interaction = create_interaction(
            conn,
            contact_id=contact_id,
            type=body.type,
            date=date.today().isoformat(),
            summary=body.summary,
            questions_detected=json.dumps(body.questions_detected or []),
            action_items=json.dumps(body.action_items or []),
        )
        conn.close()
        return interaction
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/api/pipeline/contacts/{contact_id}/rapport")
def update_rapport(contact_id: str, body: RapportUpdate):
    try:
        conn = _db()
        existing = get_contact(conn, contact_id)
        if not existing:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")
        result = update_contact(conn, contact_id, rapport_notes=body.rapport_notes)
        conn.close()
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
