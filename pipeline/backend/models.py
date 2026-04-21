"""
SQLite database layer for the sales pipeline management tool.

Uses plain sqlite3 — no ORM. All functions return plain dicts.
"""

import json
import sqlite3
from datetime import date, datetime, timedelta
from uuid import uuid4

DB_PATH = "/home/ubuntu/sundial_meetings/pipeline/backend/pipeline.db"

VALID_STAGES = (
    "new_lead", "discovery", "ballpark", "dsa",
    "design", "materials", "contract", "build",
)
VALID_TEMPERATURES = ("hot", "warm", "cold")
VALID_INTERACTION_TYPES = ("call", "email", "text", "meeting", "stage_change")
VALID_ACTION_TYPES = ("call", "email", "text")
VALID_FOLLOWUP_STATUSES = ("pending", "completed", "snoozed", "disqualified")
VALID_OUTCOMES = ("connected", "voicemail", "no_answer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _today_iso() -> str:
    return date.today().isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _parse_json_fields(d: dict, fields: tuple) -> dict:
    for f in fields:
        if f in d and d[f] is not None:
            try:
                d[f] = json.loads(d[f])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------

def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create all tables if they do not exist and return a connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS contacts (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            location          TEXT,
            stage             TEXT NOT NULL DEFAULT 'new_lead',
            temperature       TEXT DEFAULT 'warm',
            budget_range      TEXT,
            sqft              TEXT,
            style             TEXT,
            lot_status        TEXT,
            rapport_notes     TEXT,
            estimated_value   REAL,
            non_response_count INTEGER NOT NULL DEFAULT 0,
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id                TEXT PRIMARY KEY,
            contact_id        TEXT NOT NULL,
            type              TEXT NOT NULL,
            date              TEXT NOT NULL,
            summary           TEXT,
            transcript_link   TEXT,
            questions_detected TEXT,
            action_items      TEXT,
            created_at        TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        );

        CREATE TABLE IF NOT EXISTS followups (
            id                TEXT PRIMARY KEY,
            contact_id        TEXT NOT NULL,
            due_date          TEXT NOT NULL,
            reason            TEXT,
            action_type       TEXT NOT NULL,
            status            TEXT NOT NULL DEFAULT 'pending',
            completed_at      TEXT,
            outcome           TEXT,
            notes             TEXT,
            created_at        TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        );

        CREATE INDEX IF NOT EXISTS idx_interactions_contact
            ON interactions(contact_id);
        CREATE INDEX IF NOT EXISTS idx_followups_contact
            ON followups(contact_id);
        CREATE INDEX IF NOT EXISTS idx_followups_due
            ON followups(due_date, status);
        CREATE INDEX IF NOT EXISTS idx_contacts_stage
            ON contacts(stage);
    """)

    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Contacts CRUD
# ---------------------------------------------------------------------------

def create_contact(conn: sqlite3.Connection, **kwargs) -> dict:
    """Insert a new contact and return it as a dict."""
    contact_id = kwargs.get("id", str(uuid4()))
    now = _now_iso()

    stage = kwargs.get("stage", "new_lead")
    if stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage: {stage}")

    temperature = kwargs.get("temperature", "warm")
    if temperature not in VALID_TEMPERATURES:
        raise ValueError(f"Invalid temperature: {temperature}")

    conn.execute(
        """INSERT INTO contacts
           (id, name, location, stage, temperature, budget_range, sqft, style,
            lot_status, rapport_notes, estimated_value, non_response_count,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            contact_id,
            kwargs["name"],
            kwargs.get("location"),
            stage,
            temperature,
            kwargs.get("budget_range"),
            kwargs.get("sqft"),
            kwargs.get("style"),
            kwargs.get("lot_status"),
            kwargs.get("rapport_notes"),
            kwargs.get("estimated_value"),
            kwargs.get("non_response_count", 0),
            now,
            now,
        ),
    )
    conn.commit()
    return get_contact(conn, contact_id)


def get_contact(conn: sqlite3.Connection, contact_id: str) -> dict | None:
    """Fetch a single contact by ID, or None if not found."""
    row = conn.execute(
        "SELECT * FROM contacts WHERE id = ?", (contact_id,)
    ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_contacts(
    conn: sqlite3.Connection,
    stage: str | None = None,
    temperature: str | None = None,
) -> list[dict]:
    """List contacts, optionally filtered by stage and/or temperature."""
    clauses: list[str] = []
    params: list[str] = []

    if stage is not None:
        clauses.append("stage = ?")
        params.append(stage)
    if temperature is not None:
        clauses.append("temperature = ?")
        params.append(temperature)

    sql = "SELECT * FROM contacts"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_contact(conn: sqlite3.Connection, contact_id: str, **kwargs) -> dict:
    """Update specified fields on a contact and return the updated dict."""
    allowed = {
        "name", "location", "stage", "temperature", "budget_range",
        "sqft", "style", "lot_status", "rapport_notes", "estimated_value",
        "non_response_count",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_contact(conn, contact_id)

    if "stage" in updates and updates["stage"] not in VALID_STAGES:
        raise ValueError(f"Invalid stage: {updates['stage']}")
    if "temperature" in updates and updates["temperature"] not in VALID_TEMPERATURES:
        raise ValueError(f"Invalid temperature: {updates['temperature']}")

    updates["updated_at"] = _now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]

    conn.execute(
        f"UPDATE contacts SET {set_clause} WHERE id = ?", values
    )
    conn.commit()
    return get_contact(conn, contact_id)


# ---------------------------------------------------------------------------
# Interactions CRUD
# ---------------------------------------------------------------------------

def create_interaction(conn: sqlite3.Connection, **kwargs) -> dict:
    """Insert a new interaction and return it as a dict."""
    interaction_id = kwargs.get("id", str(uuid4()))
    now = _now_iso()

    interaction_type = kwargs.get("type")
    if interaction_type not in VALID_INTERACTION_TYPES:
        raise ValueError(f"Invalid interaction type: {interaction_type}")

    questions = kwargs.get("questions_detected")
    if questions is not None and not isinstance(questions, str):
        questions = json.dumps(questions)

    action_items = kwargs.get("action_items")
    if action_items is not None and not isinstance(action_items, str):
        action_items = json.dumps(action_items)

    conn.execute(
        """INSERT INTO interactions
           (id, contact_id, type, date, summary, transcript_link,
            questions_detected, action_items, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            interaction_id,
            kwargs["contact_id"],
            interaction_type,
            kwargs.get("date", _today_iso()),
            kwargs.get("summary"),
            kwargs.get("transcript_link"),
            questions,
            action_items,
            now,
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
    ).fetchone()
    d = _row_to_dict(row)
    return _parse_json_fields(d, ("questions_detected", "action_items"))


def list_interactions(
    conn: sqlite3.Connection, contact_id: str
) -> list[dict]:
    """List all interactions for a contact, newest first."""
    rows = conn.execute(
        "SELECT * FROM interactions WHERE contact_id = ? ORDER BY date DESC",
        (contact_id,),
    ).fetchall()
    return [
        _parse_json_fields(_row_to_dict(r), ("questions_detected", "action_items"))
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Follow-ups CRUD
# ---------------------------------------------------------------------------

def create_followup(conn: sqlite3.Connection, **kwargs) -> dict:
    """Insert a new follow-up and return it as a dict."""
    followup_id = kwargs.get("id", str(uuid4()))
    now = _now_iso()

    action_type = kwargs.get("action_type")
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError(f"Invalid action_type: {action_type}")

    status = kwargs.get("status", "pending")
    if status not in VALID_FOLLOWUP_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    conn.execute(
        """INSERT INTO followups
           (id, contact_id, due_date, reason, action_type, status,
            completed_at, outcome, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            followup_id,
            kwargs["contact_id"],
            kwargs["due_date"],
            kwargs.get("reason"),
            action_type,
            status,
            kwargs.get("completed_at"),
            kwargs.get("outcome"),
            kwargs.get("notes"),
            now,
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM followups WHERE id = ?", (followup_id,)
    ).fetchone()
    return _row_to_dict(row)


def get_today_queue(conn: sqlite3.Connection) -> list[dict]:
    """Return pending follow-ups due today or overdue, joined with contact info.

    Sort order:
      1. Overdue first (red), then today (amber), then this-week future
      2. Within each band, hot leads come first, then warm, then cold
    """
    today = _today_iso()
    end_of_week = (date.today() + timedelta(days=(6 - date.today().weekday()))).isoformat()

    rows = conn.execute(
        """
        SELECT
            f.id            AS followup_id,
            f.contact_id,
            f.due_date,
            f.reason,
            f.action_type,
            f.status        AS followup_status,
            f.notes         AS followup_notes,
            c.name          AS contact_name,
            c.location      AS contact_location,
            c.stage         AS contact_stage,
            c.temperature   AS contact_temperature,
            c.budget_range  AS contact_budget_range,
            c.estimated_value AS contact_estimated_value,
            c.non_response_count AS contact_non_response_count,
            CASE
                WHEN f.due_date < ? THEN 0   -- overdue  (red)
                WHEN f.due_date = ? THEN 1   -- today    (amber)
                ELSE 2                        -- this week
            END AS urgency_band,
            CASE c.temperature
                WHEN 'hot'  THEN 0
                WHEN 'warm' THEN 1
                WHEN 'cold' THEN 2
                ELSE 3
            END AS temp_rank
        FROM followups f
        JOIN contacts c ON c.id = f.contact_id
        WHERE f.status = 'pending'
          AND f.due_date <= ?
        ORDER BY urgency_band ASC, temp_rank ASC, f.due_date ASC
        """,
        (today, today, end_of_week),
    ).fetchall()

    return [_row_to_dict(r) for r in rows]


def complete_followup(
    conn: sqlite3.Connection,
    followup_id: str,
    outcome: str,
    notes: str | None = None,
) -> dict:
    """Mark a follow-up as completed."""
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Invalid outcome: {outcome}")

    now = _now_iso()
    conn.execute(
        """UPDATE followups
           SET status = 'completed', completed_at = ?, outcome = ?, notes = ?
           WHERE id = ?""",
        (now, outcome, notes, followup_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM followups WHERE id = ?", (followup_id,)
    ).fetchone()
    return _row_to_dict(row)


def snooze_followup(
    conn: sqlite3.Connection,
    followup_id: str,
    new_date: str,
) -> dict:
    """Snooze a follow-up to a new date."""
    conn.execute(
        """UPDATE followups
           SET status = 'snoozed', due_date = ?
           WHERE id = ?""",
        (new_date, followup_id),
    )
    conn.commit()

    # Re-open as pending on the new date
    conn.execute(
        """UPDATE followups
           SET status = 'pending'
           WHERE id = ?""",
        (followup_id,),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM followups WHERE id = ?", (followup_id,)
    ).fetchone()
    return _row_to_dict(row)


def disqualify_contact(
    conn: sqlite3.Connection,
    contact_id: str,
    reason: str,
) -> dict:
    """Disqualify a contact: set stage to 'new_lead' equivalent marker,
    and complete all pending follow-ups as disqualified."""
    now = _now_iso()

    # Update all pending follow-ups for this contact
    conn.execute(
        """UPDATE followups
           SET status = 'disqualified', completed_at = ?, notes = ?
           WHERE contact_id = ? AND status = 'pending'""",
        (now, f"Disqualified: {reason}", contact_id),
    )

    # Record the disqualification as a stage change interaction
    conn.execute(
        """INSERT INTO interactions
           (id, contact_id, type, date, summary, created_at)
           VALUES (?, ?, 'stage_change', ?, ?, ?)""",
        (str(uuid4()), contact_id, _today_iso(), f"Disqualified: {reason}", now),
    )

    conn.commit()
    return get_contact(conn, contact_id)


# ---------------------------------------------------------------------------
# Reporting / Summaries
# ---------------------------------------------------------------------------

def get_pipeline_summary(conn: sqlite3.Connection) -> dict:
    """Return a dict with counts and total estimated_value per stage."""
    rows = conn.execute(
        """SELECT stage,
                  COUNT(*)                AS count,
                  COALESCE(SUM(estimated_value), 0) AS total_value
           FROM contacts
           GROUP BY stage
           ORDER BY stage"""
    ).fetchall()

    summary: dict = {}
    for r in rows:
        d = _row_to_dict(r)
        summary[d["stage"]] = {
            "count": d["count"],
            "total_value": d["total_value"],
        }

    # Ensure every valid stage appears even if count is 0
    for s in VALID_STAGES:
        if s not in summary:
            summary[s] = {"count": 0, "total_value": 0}

    return summary


def get_overdue_count(conn: sqlite3.Connection) -> int:
    """Return the number of pending follow-ups that are overdue."""
    row = conn.execute(
        """SELECT COUNT(*) AS cnt
           FROM followups
           WHERE status = 'pending' AND due_date < ?""",
        (_today_iso(),),
    ).fetchone()
    return row["cnt"]
