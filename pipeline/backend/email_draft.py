"""
AI-powered follow-up email draft generator using Claude Haiku.

Generates personalised follow-up emails for Golden Eagle Log Homes sales reps
via Claude tool-use, with a template-based fallback for offline/error scenarios.
"""

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "services"))

from anthropic_client import call_with_retry, extract_tool_use

log = logging.getLogger("email_draft")

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You draft follow-up emails for sales reps at Golden Eagle Log Homes "
    "(luxury custom log homes).\n\n"
    "Guidelines:\n"
    "- Reference specific topics from the last conversation\n"
    "- Include relevant link placeholders like [FLOOR_PLAN_LINK] or "
    "[YOUTUBE_VIDEO_LINK] where appropriate\n"
    "- Tone: warm, professional, consultative — not pushy\n"
    "- Keep it concise — 3-5 short paragraphs\n"
    "- End with a clear next step or question\n"
    "- The rep will edit before sending, so get the structure right"
)

DRAFT_EMAIL_TOOL = {
    "name": "draft_email",
    "description": (
        "Return a structured follow-up email draft for a sales rep to review."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": (
                    "The email body, plain text, 3-5 paragraphs max"
                ),
            },
            "send_date_suggestion": {
                "type": "string",
                "description": (
                    "ISO date for suggested send time, e.g. tomorrow morning"
                ),
            },
        },
        "required": ["subject", "body", "send_date_suggestion"],
    },
}


def _build_user_message(contact: dict, interactions: list, followups: list) -> str:
    """Assemble the user prompt from contact data, interactions, and followups."""
    parts = []

    name = contact.get("name", "the contact")
    parts.append(f"Contact: {name}")
    if contact.get("email"):
        parts.append(f"Email: {contact['email']}")
    if contact.get("company"):
        parts.append(f"Company: {contact['company']}")

    if interactions:
        parts.append("\nRecent interactions:")
        for ix in interactions:
            summary = ix.get("summary", ix.get("notes", ""))
            ix_date = ix.get("date", "")
            parts.append(f"  - [{ix_date}] {summary}")

    if followups:
        parts.append("\nPending follow-ups:")
        for fu in followups:
            action = fu.get("action", fu.get("description", ""))
            fu_date = fu.get("due_date", "")
            parts.append(f"  - [{fu_date}] {action}")

    parts.append(
        "\nPlease draft a follow-up email using the draft_email tool."
    )
    return "\n".join(parts)


def generate_email_draft(
    contact: dict, interactions: list, followups: list
) -> dict:
    """
    Generate an AI-powered follow-up email draft via Claude Haiku tool-use.

    Parameters
    ----------
    contact : dict
        Contact record with at least ``name``; may include ``email``, ``company``.
    interactions : list[dict]
        Recent interaction records (``date``, ``summary`` / ``notes``).
    followups : list[dict]
        Pending follow-up items (``due_date``, ``action`` / ``description``).

    Returns
    -------
    dict
        Keys: ``subject``, ``body``, ``send_date_suggestion``, ``source``
        (``"ai"`` when Claude succeeds, ``"template"`` on fallback).
    """
    try:
        user_message = _build_user_message(contact, interactions, followups)

        response = call_with_retry(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=[DRAFT_EMAIL_TOOL],
            tool_choice={"type": "tool", "name": "draft_email"},
            messages=[{"role": "user", "content": user_message}],
        )

        tool_block = extract_tool_use(response)
        if tool_block is None:
            log.warning("No tool_use block in response — falling back to template")
            return generate_email_simple(
                contact,
                interactions[0] if interactions else {},
            )

        result = tool_block.input
        return {
            "subject": result.get("subject", ""),
            "body": result.get("body", ""),
            "send_date_suggestion": result.get("send_date_suggestion", ""),
            "source": "ai",
        }

    except Exception:
        log.exception("Email draft generation failed — using template fallback")
        return generate_email_simple(
            contact,
            interactions[0] if interactions else {},
        )


def generate_email_simple(contact: dict, last_interaction: dict) -> dict:
    """
    Template-based fallback email draft that works offline (no Claude call).

    Parameters
    ----------
    contact : dict
        Contact record with at least ``name``.
    last_interaction : dict
        Most recent interaction (``summary`` / ``notes``, ``date``).

    Returns
    -------
    dict
        Keys: ``subject``, ``body``, ``send_date_suggestion``, ``source``.
    """
    name = contact.get("name", "there")
    first_name = name.split()[0] if name and name != "there" else name

    topic = last_interaction.get(
        "summary", last_interaction.get("notes", "our recent conversation")
    )
    last_date = last_interaction.get("date", "recently")

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    subject = "Following up on our conversation \u2014 Golden Eagle Log Homes"

    body = (
        f"Hi {first_name},\n\n"
        f"Thank you for taking the time to speak with us {last_date}. "
        f"I enjoyed learning more about what you're looking for and wanted "
        f"to follow up on {topic}.\n\n"
        f"I've put together some resources that I think you'll find helpful, "
        f"including a few floor plans that align with what we discussed "
        f"[FLOOR_PLAN_LINK]. We also have a short video walkthrough of a "
        f"similar project that might give you a feel for the finished product "
        f"[YOUTUBE_VIDEO_LINK].\n\n"
        f"Please don't hesitate to reach out if any questions come to mind. "
        f"I'd love to set up a time to walk through the options together "
        f"and make sure we find the perfect fit for your vision.\n\n"
        f"Looking forward to hearing from you.\n\n"
        f"Warm regards,\n"
        f"[YOUR_NAME]\n"
        f"Golden Eagle Log & Timber Homes"
    )

    return {
        "subject": subject,
        "body": body,
        "send_date_suggestion": tomorrow,
        "source": "template",
    }
