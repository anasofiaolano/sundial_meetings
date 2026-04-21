"""
pipeline/backend/briefing.py

AI-powered "Before You Call" briefing card generator using Claude Haiku.
Produces structured pre-call briefing cards so sales reps can prep in 15 seconds.
"""

import json
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent  # sundial_meetings/
sys.path.insert(0, str(ROOT_DIR / "services"))

from anthropic_client import call_with_retry, extract_tool_use

log = logging.getLogger("briefing")

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512

BRIEFING_TOOL = {
    "name": "generate_briefing",
    "description": (
        "Return a structured pre-call briefing card for a sales rep."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "last_conversation": {
                "type": "string",
                "description": "1-2 sentence summary of the last interaction.",
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Questions from the prospect still unanswered.",
            },
            "rapport_hooks": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Personal details to reference for rapport.",
            },
            "whats_new": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Relevant updates since last touch.",
            },
            "talking_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-3 suggested talking points for the call.",
            },
        },
        "required": [
            "last_conversation",
            "open_questions",
            "rapport_hooks",
            "whats_new",
            "talking_points",
        ],
    },
}

SYSTEM_PROMPT = (
    "You generate pre-call briefing cards for sales reps. "
    "Use the contact's interaction history to summarize the last conversation. "
    "Pull open questions from interactions that have questions_detected. "
    "Extract personal details from rapport_notes and interaction summaries. "
    "Suggest talking points based on the prospect's stage and recent activity. "
    "Keep everything concise — the rep reads this in 15 seconds."
)

_FALLBACK = {
    "last_conversation": "No briefing available.",
    "open_questions": [],
    "rapport_hooks": [],
    "whats_new": [],
    "talking_points": ["Introduce yourself and your product."],
}


def _build_user_message(
    contact: dict,
    interactions: list,
    followups: list | None = None,
) -> str:
    """Assemble the user prompt from contact data, interactions, and followups."""
    parts = [
        f"Contact: {contact.get('name', 'Unknown')}",
        f"Company: {contact.get('company', 'Unknown')}",
        f"Title: {contact.get('title', 'Unknown')}",
        f"Stage: {contact.get('stage', 'Unknown')}",
    ]

    if interactions:
        parts.append("\n--- Interaction History (most recent first) ---")
        for ix in interactions:
            parts.append(
                f"- [{ix.get('date', '?')}] {ix.get('channel', '?')}: "
                f"{ix.get('summary', 'No summary')}"
            )
            if ix.get("questions_detected"):
                parts.append(
                    f"  Questions: {json.dumps(ix['questions_detected'])}"
                )
            if ix.get("rapport_notes"):
                parts.append(f"  Rapport: {ix['rapport_notes']}")
    else:
        parts.append("\nNo prior interactions on record.")

    if followups:
        parts.append("\n--- Pending Follow-ups ---")
        for fu in followups:
            parts.append(
                f"- [{fu.get('due_date', '?')}] {fu.get('description', 'No description')}"
            )

    return "\n".join(parts)


def generate_briefing(
    contact: dict,
    interactions: list,
    followups: list | None = None,
) -> dict:
    """
    Call Claude Haiku to produce a structured pre-call briefing card.

    Parameters
    ----------
    contact : dict
        Contact record with keys like name, company, title, stage.
    interactions : list
        Recent interactions sorted newest-first. Each may contain summary,
        questions_detected, rapport_notes, date, channel.
    followups : list | None
        Pending follow-up items with due_date and description.

    Returns
    -------
    dict  with keys: last_conversation, open_questions, rapport_hooks,
          whats_new, talking_points.
    """
    user_message = _build_user_message(contact, interactions, followups)

    try:
        response = call_with_retry(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[BRIEFING_TOOL],
            tool_choice={"type": "tool", "name": "generate_briefing"},
            messages=[{"role": "user", "content": user_message}],
        )

        tool_block = extract_tool_use(response)
        if tool_block is None:
            log.warning("No tool_use block in briefing response; using fallback.")
            return dict(_FALLBACK)

        return tool_block.input

    except Exception:
        log.exception("Briefing generation failed; returning fallback.")
        return dict(_FALLBACK)


# ------------------------------------------------------------------
# Simple (non-AI) fallback
# ------------------------------------------------------------------

def generate_briefing_simple(
    contact: dict,
    interactions: list,
) -> dict:
    """
    Build a briefing card from raw data without calling Claude.
    Fast fallback when the AI path is unavailable or unnecessary.

    Parameters
    ----------
    contact : dict
        Contact record.
    interactions : list
        Recent interactions sorted newest-first.

    Returns
    -------
    dict  with the same shape as generate_briefing output.
    """
    # Last conversation
    if interactions:
        latest = interactions[0]
        last_conversation = (
            f"{latest.get('channel', 'Touch')} on {latest.get('date', '?')}: "
            f"{latest.get('summary', 'No summary available.')}"
        )
    else:
        last_conversation = "No previous interactions on record."

    # Open questions — collect from all interactions
    open_questions: list[str] = []
    for ix in interactions:
        for q in ix.get("questions_detected") or []:
            if q and q not in open_questions:
                open_questions.append(q)

    # Rapport hooks — collect rapport_notes
    rapport_hooks: list[str] = []
    for ix in interactions:
        note = ix.get("rapport_notes")
        if note and note not in rapport_hooks:
            rapport_hooks.append(note)

    # What's new — use follow-ups or recent interactions beyond the first
    whats_new: list[str] = []
    for ix in interactions[1:4]:
        whats_new.append(
            f"{ix.get('date', '?')}: {ix.get('summary', 'Activity recorded.')}"
        )

    # Stage-appropriate talking points
    stage = (contact.get("stage") or "").lower()
    if "demo" in stage or "evaluation" in stage:
        talking_points = [
            "Ask about their evaluation criteria.",
            "Offer a tailored demo based on their use case.",
            "Discuss timeline and decision process.",
        ]
    elif "negotiation" in stage or "proposal" in stage:
        talking_points = [
            "Review proposal terms and address concerns.",
            "Confirm budget and decision-maker involvement.",
            "Discuss next steps toward close.",
        ]
    elif "closed" in stage or "won" in stage:
        talking_points = [
            "Check in on onboarding progress.",
            "Ask about early wins or challenges.",
            "Identify expansion or referral opportunities.",
        ]
    elif "prospect" in stage or "lead" in stage:
        talking_points = [
            "Understand their current pain points.",
            "Share a relevant success story.",
            "Propose a concrete next step.",
        ]
    else:
        talking_points = [
            "Reintroduce yourself and recap last touch.",
            "Ask what has changed since you last spoke.",
            "Suggest a clear next action.",
        ]

    return {
        "last_conversation": last_conversation,
        "open_questions": open_questions,
        "rapport_hooks": rapport_hooks,
        "whats_new": whats_new,
        "talking_points": talking_points,
    }
