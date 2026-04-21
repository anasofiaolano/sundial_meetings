"""
Automated follow-up scheduling engine.

Generates follow-ups based on contact stage, temperature, and interaction
history.  All logic is rule-based (no AI calls) so it runs instantly and
deterministically.
"""

from datetime import date, datetime, timedelta

from models import (
    DB_PATH,
    get_contact,
    list_interactions,
    create_followup,
    _today_iso,
)


# ---------------------------------------------------------------------------
# Cadence rules
# ---------------------------------------------------------------------------

_ACTIVE_STAGES = ("dsa", "design", "materials")
_DISCOVERY_STAGES = ("discovery", "ballpark")
_CHECKIN_STAGES = ("contract", "build")


def get_cadence(temperature: str, stage: str) -> int:
    """Return the number of days until the next follow-up.

    Rules (evaluated top-to-bottom, first match wins):
      - new_lead (any temp)              ->  3 days
      - contract / build (any temp)      -> 14 days
      - hot + any active stage           ->  7 days
      - warm + dsa / design / materials  ->  7 days
      - warm + discovery / ballpark      -> 14 days
      - cold + any                       -> 90 days
    """
    if stage == "new_lead":
        return 3

    if stage in _CHECKIN_STAGES:
        return 14

    if temperature == "hot":
        return 7

    if temperature == "warm":
        if stage in _ACTIVE_STAGES:
            return 7
        return 14  # discovery / ballpark

    if temperature == "cold":
        return 90

    # Fallback for unknown combos
    return 14


# ---------------------------------------------------------------------------
# Action-type suggestion
# ---------------------------------------------------------------------------

def suggest_action_type(
    contact: dict,
    last_interaction: dict | None,
) -> str:
    """Suggest the next action type (call / email / text).

    Priority:
      1. If the contact has a ``preferred_method``, honour it.
      2. Alternate between call and email based on the last interaction.
      3. Default to call when there is no history.
    """
    preferred = contact.get("preferred_method")
    if preferred in ("call", "email", "text"):
        return preferred

    if last_interaction is None:
        return "call"

    last_type = last_interaction.get("type", "")
    if last_type == "call":
        return "email"
    if last_type == "email":
        return "call"

    # For meetings, texts, stage_changes, etc. default to call
    return "call"


# ---------------------------------------------------------------------------
# Reason generation (template-based, AI-free)
# ---------------------------------------------------------------------------

def generate_followup_reason(
    contact: dict,
    last_interaction: dict | None,
) -> str:
    """Build a human-readable reason string for the follow-up."""
    stage = contact.get("stage", "new_lead")

    # --- No prior interaction ---
    if last_interaction is None:
        return "Initial follow-up \u2014 qualify on budget and timeline"

    last_date_str = last_interaction.get("date", "")
    days_since = _days_since(last_date_str)

    # --- Stage-specific templates ---
    if stage == "new_lead":
        return "Initial follow-up \u2014 qualify on budget and timeline"

    if stage == "ballpark":
        return (
            f"Ballpark follow-up \u2014 sent estimate on {last_date_str}, "
            "check reaction"
        )

    if stage == "design":
        # Try to infer revision number from summary
        revision = _extract_revision(last_interaction)
        if revision:
            return (
                f"Design check-in \u2014 revision {revision} submitted, "
                "get feedback"
            )
        return "Design check-in \u2014 get feedback on latest revision"

    if stage == "discovery":
        topic = _extract_question_topic(last_interaction)
        if topic:
            return f"Discovery follow-up \u2014 asked about {topic}"
        return "Discovery follow-up \u2014 continue qualifying conversation"

    # --- Overdue catch-all ---
    if days_since is not None and days_since >= 30:
        return f"Overdue \u2014 last contact {days_since} days ago"

    # --- Style-aware touch for nurture ---
    style = contact.get("style")
    if style and days_since is not None and days_since >= 14:
        return f"YouTube touch \u2014 new video relevant to {style} homes"

    # --- Generic 30-day check-in ---
    topic = _extract_question_topic(last_interaction)
    if topic:
        return f"30-day check-in \u2014 asked about {topic}"

    return "Scheduled follow-up \u2014 maintain contact cadence"


# ---------------------------------------------------------------------------
# Schedule next follow-up
# ---------------------------------------------------------------------------

def schedule_next_followup(conn, contact_id: str) -> dict:
    """Read the contact, compute cadence, and insert a new pending follow-up.

    Returns the created follow-up dict.
    """
    contact = get_contact(conn, contact_id)
    if contact is None:
        raise ValueError(f"Contact not found: {contact_id}")

    interactions = list_interactions(conn, contact_id)
    last_interaction = interactions[0] if interactions else None

    cadence_days = get_cadence(
        contact.get("temperature", "warm"),
        contact.get("stage", "new_lead"),
    )

    due_date = (date.today() + timedelta(days=cadence_days)).isoformat()
    action_type = suggest_action_type(contact, last_interaction)
    reason = generate_followup_reason(contact, last_interaction)

    followup = create_followup(
        conn,
        contact_id=contact_id,
        due_date=due_date,
        action_type=action_type,
        reason=reason,
    )
    return followup


# ---------------------------------------------------------------------------
# Disqualification check
# ---------------------------------------------------------------------------

def check_disqualification(conn, contact_id: str) -> bool:
    """Return True if the contact has >= 6 consecutive non-responses.

    A non-response is a completed follow-up whose outcome is ``no_answer``
    or ``voicemail``.  The streak resets whenever an outcome of
    ``connected`` appears.
    """
    rows = conn.execute(
        """SELECT outcome
           FROM followups
           WHERE contact_id = ?
             AND status = 'completed'
             AND outcome IS NOT NULL
           ORDER BY completed_at DESC""",
        (contact_id,),
    ).fetchall()

    streak = 0
    for row in rows:
        outcome = row["outcome"]
        if outcome == "connected":
            break
        if outcome in ("no_answer", "voicemail"):
            streak += 1

    return streak >= 6


# ---------------------------------------------------------------------------
# Stale / nurture-pool contacts
# ---------------------------------------------------------------------------

def get_stale_contacts(conn, days: int = 90) -> list[dict]:
    """Return contacts with no interaction in the last *days* days.

    These are candidates for the nurture pool.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        """SELECT c.*
           FROM contacts c
           LEFT JOIN (
               SELECT contact_id, MAX(date) AS last_date
               FROM interactions
               GROUP BY contact_id
           ) i ON i.contact_id = c.id
           WHERE i.last_date IS NULL
              OR i.last_date <= ?
           ORDER BY i.last_date ASC""",
        (cutoff,),
    ).fetchall()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _days_since(date_str: str) -> int | None:
    """Return the number of days between *date_str* and today, or None."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(date_str[:10])
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


def _extract_question_topic(interaction: dict) -> str | None:
    """Pull the first detected question topic from an interaction, if any."""
    questions = interaction.get("questions_detected")
    if isinstance(questions, list) and questions:
        first = questions[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("topic") or first.get("question")
    if isinstance(questions, str) and questions:
        return questions
    return None


def _extract_revision(interaction: dict) -> str | None:
    """Try to pull a revision number from the interaction summary."""
    summary = interaction.get("summary", "") or ""
    lower = summary.lower()
    for marker in ("revision ", "rev ", "v"):
        idx = lower.find(marker)
        if idx != -1:
            rest = summary[idx + len(marker):].strip()
            num = ""
            for ch in rest:
                if ch.isdigit():
                    num += ch
                else:
                    break
            if num:
                return num
    return None
