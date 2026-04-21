"""
Main FastAPI router that combines all pipeline sub-routers and serves frontend pages.

Aggregates:
  - routes_today    (today action queue)
  - routes_pipeline (kanban stages, summary, stage moves)
  - routes_contacts (contact CRUD, interactions, rapport)

Also exposes:
  - GET  /api/pipeline/contacts/{contact_id}/briefing   -- pre-call briefing card
  - POST /api/pipeline/contacts/{contact_id}/email-draft -- email draft generation
  - Frontend page routes under /pipeline/*
"""

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PIPELINE_DIR = Path(__file__).parent
FRONTEND_DIR = PIPELINE_DIR.parent / "frontend"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from routes_today import router as today_router
from routes_pipeline import router as pipeline_router
from routes_contacts import router as contacts_router
from models import init_db

# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

DB_PATH = PIPELINE_DIR / "pipeline.db"
init_db(str(DB_PATH))

log = logging.getLogger("pipeline.router")

# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

pipeline_main_router = APIRouter()

# Include sub-routers
pipeline_main_router.include_router(today_router)
pipeline_main_router.include_router(pipeline_router)
pipeline_main_router.include_router(contacts_router)


# ---------------------------------------------------------------------------
# Database helper
# ---------------------------------------------------------------------------


def _get_db() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Frontend page routes
# ---------------------------------------------------------------------------


@pipeline_main_router.get("/pipeline")
async def serve_today():
    """Serve the today / action-queue page."""
    try:
        html_path = FRONTEND_DIR / "today.html"
        if not html_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="today.html not found in frontend directory",
            )
        return FileResponse(html_path)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to serve today page")
        raise HTTPException(status_code=500, detail=str(exc))


@pipeline_main_router.get("/pipeline/kanban")
async def serve_pipeline():
    """Serve the kanban / pipeline board page."""
    try:
        html_path = FRONTEND_DIR / "pipeline.html"
        if not html_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="pipeline.html not found in frontend directory",
            )
        return FileResponse(html_path)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to serve pipeline page")
        raise HTTPException(status_code=500, detail=str(exc))


@pipeline_main_router.get("/pipeline/contact/{contact_id}")
async def serve_contact(contact_id: str):
    """Serve the contact detail page."""
    try:
        html_path = FRONTEND_DIR / "contact.html"
        if not html_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="contact.html not found in frontend directory",
            )
        return FileResponse(html_path)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to serve contact page")
        raise HTTPException(status_code=500, detail=str(exc))


@pipeline_main_router.get("/pipeline/review/{call_id}")
async def serve_review(call_id: str):
    """Serve the call review page."""
    try:
        html_path = FRONTEND_DIR / "review.html"
        if not html_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="review.html not found in frontend directory",
            )
        return FileResponse(html_path)
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Failed to serve review page")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Briefing endpoint
# ---------------------------------------------------------------------------


@pipeline_main_router.get("/api/pipeline/contacts/{contact_id}/briefing")
async def get_briefing(
    contact_id: str,
    ai: Optional[bool] = Query(
        default=False,
        description="Use AI-powered briefing (slower, richer). Default is simple/fast.",
    ),
):
    """
    Generate a pre-call briefing card for a contact.

    Query params:
      ?ai=true  -- use Claude Haiku for richer briefing (requires API key)
      default   -- fast rule-based briefing from raw data
    """
    try:
        conn = _get_db()

        # Fetch contact
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")
        contact = dict(row)

        # Fetch interactions (newest first)
        ix_rows = conn.execute(
            "SELECT * FROM interactions WHERE contact_id = ? ORDER BY date DESC",
            (contact_id,),
        ).fetchall()
        interactions = [dict(r) for r in ix_rows]

        # Fetch pending followups
        fu_rows = conn.execute(
            "SELECT * FROM followups WHERE contact_id = ? AND status = 'pending' "
            "ORDER BY due_date ASC",
            (contact_id,),
        ).fetchall()
        followups = [dict(r) for r in fu_rows]

        conn.close()

        if ai:
            try:
                from briefing import generate_briefing

                briefing = generate_briefing(contact, interactions, followups)
            except ImportError:
                log.warning(
                    "briefing module not available; falling back to simple briefing"
                )
                from briefing import generate_briefing_simple

                briefing = generate_briefing_simple(contact, interactions)
            except Exception:
                log.exception("AI briefing failed; falling back to simple briefing")
                from briefing import generate_briefing_simple

                briefing = generate_briefing_simple(contact, interactions)
        else:
            from briefing import generate_briefing_simple

            briefing = generate_briefing_simple(contact, interactions)

        return {"contact_id": contact_id, "briefing": briefing}

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Briefing endpoint failed for contact %s", contact_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Email draft endpoint
# ---------------------------------------------------------------------------


def _generate_email_draft_simple(contact: dict, interactions: list) -> dict:
    """
    Build a simple follow-up email draft from contact data without calling an LLM.

    Returns a dict with keys: subject, body, tone.
    """
    name = contact.get("name", "there")
    first_name = name.split()[0] if name else "there"
    stage = (contact.get("stage") or "").lower()

    # Determine tone and content from stage
    if "new_lead" in stage or "discovery" in stage:
        subject = f"Great connecting with you, {first_name}"
        tone = "warm-intro"
        opening = (
            f"Hi {first_name},\n\n"
            "It was great connecting with you. I wanted to follow up on our "
            "conversation and see if you had any questions."
        )
    elif "ballpark" in stage or "dsa" in stage:
        subject = f"Next steps on your project, {first_name}"
        tone = "consultative"
        opening = (
            f"Hi {first_name},\n\n"
            "I hope you're doing well. I wanted to touch base regarding the "
            "next steps we discussed for your project."
        )
    elif "design" in stage or "materials" in stage:
        subject = f"Design progress update, {first_name}"
        tone = "professional"
        opening = (
            f"Hi {first_name},\n\n"
            "I wanted to share a quick update on where things stand with "
            "your project design and materials."
        )
    elif "contract" in stage or "build" in stage:
        subject = f"Moving forward, {first_name}"
        tone = "closing"
        opening = (
            f"Hi {first_name},\n\n"
            "Great news -- we're making solid progress. I wanted to follow up "
            "on the details we discussed to keep things moving."
        )
    else:
        subject = f"Following up, {first_name}"
        tone = "neutral"
        opening = (
            f"Hi {first_name},\n\n"
            "I hope this message finds you well. I wanted to follow up and "
            "see how things are going on your end."
        )

    # Add context from recent interaction if available
    context_line = ""
    if interactions:
        latest = interactions[0]
        summary = latest.get("summary")
        if summary:
            context_line = (
                f"\nLast time we spoke, we discussed: {summary}\n"
            )

    closing = (
        "\nPlease let me know if you have any questions or if there's "
        "a good time to connect this week.\n\n"
        "Best regards"
    )

    body = opening + context_line + closing

    return {"subject": subject, "body": body, "tone": tone}


@pipeline_main_router.post("/api/pipeline/contacts/{contact_id}/email-draft")
async def get_email_draft(
    contact_id: str,
    ai: Optional[bool] = Query(
        default=False,
        description="Use AI-powered draft (slower, richer). Default is simple/fast.",
    ),
):
    """
    Generate a follow-up email draft for a contact.

    Query params:
      ?ai=true  -- use Claude for richer email draft (requires API key)
      default   -- fast template-based draft from raw data
    """
    try:
        conn = _get_db()

        # Fetch contact
        row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Contact not found")
        contact = dict(row)

        # Fetch interactions (newest first)
        ix_rows = conn.execute(
            "SELECT * FROM interactions WHERE contact_id = ? ORDER BY date DESC",
            (contact_id,),
        ).fetchall()
        interactions = [dict(r) for r in ix_rows]

        conn.close()

        if ai:
            try:
                # Attempt AI-powered email draft via briefing module as context
                from briefing import generate_briefing

                briefing = generate_briefing(contact, interactions)
                # Build a richer draft informed by the AI briefing
                name = contact.get("name", "there")
                first_name = name.split()[0] if name else "there"
                subject = f"Following up - {first_name}"
                body_parts = [f"Hi {first_name},\n"]

                if briefing.get("last_conversation"):
                    body_parts.append(
                        f"Regarding our last conversation: "
                        f"{briefing['last_conversation']}\n"
                    )

                if briefing.get("talking_points"):
                    body_parts.append(
                        "I wanted to touch on a few things:\n"
                    )
                    for point in briefing["talking_points"]:
                        body_parts.append(f"  - {point}")
                    body_parts.append("")

                if briefing.get("open_questions"):
                    body_parts.append(
                        "I also wanted to address the questions you raised:\n"
                    )
                    for q in briefing["open_questions"]:
                        body_parts.append(f"  - {q}")
                    body_parts.append("")

                body_parts.append(
                    "Let me know a good time to connect and discuss further."
                    "\n\nBest regards"
                )

                draft = {
                    "subject": subject,
                    "body": "\n".join(body_parts),
                    "tone": "ai-generated",
                }
            except ImportError:
                log.warning(
                    "briefing module not available; falling back to simple draft"
                )
                draft = _generate_email_draft_simple(contact, interactions)
            except Exception:
                log.exception("AI email draft failed; falling back to simple draft")
                draft = _generate_email_draft_simple(contact, interactions)
        else:
            draft = _generate_email_draft_simple(contact, interactions)

        return {"contact_id": contact_id, "draft": draft}

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Email draft endpoint failed for contact %s", contact_id)
        raise HTTPException(status_code=500, detail=str(exc))
