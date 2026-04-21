# chat.py
#
# Production chat module for /api/chat.
# Converted from phase-7-chat/chat_context_test.ipynb.
#
# Usage (non-streaming):
#   from phase_7_chat.chat import chat_complete
#   result = chat_complete(messages=[...], context_items=[...])
#
# Usage (streaming, for FastAPI StreamingResponse):
#   from phase_7_chat.chat import chat_stream
#   async for chunk in chat_stream(messages=[...], context_items=[...]):
#       yield chunk

import json
import sqlite3
import sys
from pathlib import Path
from typing import Iterator

# ── Path setup ─────────────────────────────────────────────────────────────────
# This file lives in phase-7-chat/; adjust imports relative to sundial_meetings/
CHAT_DIR  = Path(__file__).parent          # phase-7-chat/
ROOT_DIR  = CHAT_DIR.parent               # sundial_meetings/
BACKEND_DIR  = ROOT_DIR / "backend"
NOTES_DIR    = ROOT_DIR / "dummy_data" / "notes"
SERVICES_DIR = ROOT_DIR / "services"
DB_PATH      = BACKEND_DIR / "jobs.db"

for p in (str(SERVICES_DIR), str(ROOT_DIR / "utils")):
    if p not in sys.path:
        sys.path.insert(0, p)

from anthropic_client import call_with_retry, stream_with_retry  # noqa: E402


# ── 1. Config & Pricing ────────────────────────────────────────────────────────

MODEL      = "claude-sonnet-4-6"   # quality > speed for conversational use (phase-7 spec)
MAX_OUTPUT = 1_024                 # tokens — sufficient for concise chat answers

# Sonnet 4.6 pricing (April 2026)
INPUT_PRICE_PER_M  = 3.00   # USD per 1M input tokens
OUTPUT_PRICE_PER_M = 15.00  # USD per 1M output tokens

# Token budget thresholds (confirmed by notebook stress test: all 13 calls = 102k tokens)
BUDGET_WARNING  = 60_000   # above this: consider dropping transcripts
BUDGET_HARD_CAP = 150_000  # above this: must drop transcripts

SYSTEM_PREFIX = """\
You are an AI assistant embedded in Sundial, a consulting call management tool.
You help consultants understand their calls and project notes.
Be concise, factual, and grounded in the provided context.
If the answer isn't in the context, say so — don't speculate.\
"""


# ── 2. DB Helpers ──────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _load_job(job_id: str) -> sqlite3.Row | None:
    """Return the DB row for a job, or None if not found."""
    conn = _connect()
    row  = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return row


# ── 3. Context Loaders ─────────────────────────────────────────────────────────

def load_call_context(job_id: str, include_transcript: bool = True) -> str:
    """
    Format one call as a context block for the system prompt.

    Loads briefing from the DB and transcript from the run folder.
    Falls back to briefing-only if the transcript file is missing.

    Returns a string ready to be appended to the system prompt.
    """
    row = _load_job(job_id)
    if not row:
        raise ValueError(f"Job {job_id} not found in DB")

    name = row["transcript_name"] or ""
    date = (row["created_at"] or "")[:10]

    parts = [f"## Call: {name} ({date})"]

    # Briefing sections — skip engagement_context (internal scaffolding)
    if row["briefing"]:
        try:
            b = json.loads(row["briefing"])
        except Exception:
            b = {}
        for section, label in [
            ("summary",      "Summary"),
            ("attendees",    "Attendees"),
            ("topics",       "Topics"),
            ("key_items",    "Key Items"),
            ("action_items", "Action Items"),
            ("email_draft",  "Follow-up Email Draft"),
        ]:
            if b.get(section):
                parts.append(f"\n### {label}\n{b[section]}")

    # Full transcript (optional)
    if include_transcript:
        run_dir = Path(row["run_dir"]) if row["run_dir"] else None
        run_dir = run_dir if run_dir and run_dir.exists() else None
        tx_file = run_dir / "transcript.txt" if run_dir else None
        if tx_file and tx_file.exists():
            parts.append(f"\n### Full Transcript\n{tx_file.read_text(encoding='utf-8')}")
        else:
            parts.append("\n### Full Transcript\n(not available)")

    return "\n".join(parts)


def load_file_context(rel: str) -> str:
    """
    Format one project file as a context block for the system prompt.

    `rel` is relative to NOTES_DIR, e.g. 'people/jay-eichinger.md'

    Returns a string ready to be appended to the system prompt.
    """
    path = NOTES_DIR / rel
    if not path.exists():
        raise FileNotFoundError(f"Project file not found: {rel}")
    return f"## Project File: {rel}\n\n{path.read_text(encoding='utf-8')}"


# ── 4. System Prompt Assembly ──────────────────────────────────────────────────

def build_system_prompt(context_items: list[dict]) -> str:
    """
    Assemble the full system prompt from a list of context items.

    Each item is a dict:
      { "type": "call", "id": "<job_id>" }
      { "type": "file", "rel": "people/jay-eichinger.md" }

    Automatic budget management:
      - Total tokens estimated by char count (÷4).
      - Above BUDGET_WARNING: transcripts are dropped, briefings only.
      - Above BUDGET_HARD_CAP: same — hard enforcement.
      - A warning comment is injected into the system prompt when transcripts are dropped.

    Returns the assembled system prompt string.
    """
    if not context_items:
        return SYSTEM_PREFIX

    # Estimate token cost of full context (transcripts included) to decide budget
    char_estimate = 0
    for item in context_items:
        if item.get("type") == "call":
            try:
                char_estimate += len(load_call_context(item["id"], include_transcript=True))
            except Exception:
                pass
        elif item.get("type") == "file":
            try:
                char_estimate += len(load_file_context(item["rel"]))
            except Exception:
                pass

    estimated_tokens   = char_estimate // 4
    include_transcripts = estimated_tokens < BUDGET_WARNING

    blocks = [SYSTEM_PREFIX, "\n\n# Context"]

    if not include_transcripts:
        blocks.append(
            "\n\n[Note: transcripts omitted to fit context — briefings only. "
            "Answers are based on summaries, not full transcripts.]"
        )

    for item in context_items:
        try:
            if item.get("type") == "call":
                blocks.append("\n" + load_call_context(item["id"], include_transcript=include_transcripts))
            elif item.get("type") == "file":
                blocks.append("\n" + load_file_context(item["rel"]))
        except Exception as e:
            # Missing context item — inject a note rather than aborting
            blocks.append(f"\n[Context item unavailable: {e}]")

    return "\n".join(blocks)


# ── 5. Cost Calculation ────────────────────────────────────────────────────────

def calculate_cost(input_tokens: int, output_tokens: int) -> dict:
    """
    Calculate API cost for one request.

    Returns:
        {
          "input_tokens":  int,
          "output_tokens": int,
          "cost_usd":      float,   # total cost, rounded to 4 decimal places
          "cost_str":      str,     # formatted as "~$0.018" (3 decimal places, min $0.001)
        }
    """
    cost = (
        input_tokens  / 1_000_000 * INPUT_PRICE_PER_M +
        output_tokens / 1_000_000 * OUTPUT_PRICE_PER_M
    )
    cost_rounded = round(cost, 4)

    # Display: 3 decimal places, floor at $0.001 so we never show "$0.000"
    display = max(cost_rounded, 0.001)
    cost_str = f"~${display:.3f}"

    return {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cost_usd":      cost_rounded,
        "cost_str":      cost_str,
    }


# ── 6. Non-Streaming Chat ──────────────────────────────────────────────────────

def chat_complete(
    messages:      list[dict],
    context_items: list[dict] | None = None,
) -> dict:
    """
    Send a chat request and return the full response.

    Args:
        messages:      Conversation history — [{"role": "user"|"assistant", "content": str}, ...]
        context_items: Optional list of context items — see build_system_prompt().

    Returns:
        {
          "content": str,             # assistant's reply
          "usage":   {                # token & cost breakdown
              "input_tokens":  int,
              "output_tokens": int,
              "cost_usd":      float,
              "cost_str":      str,
          }
        }
    """
    system = build_system_prompt(context_items or [])

    response = call_with_retry( # should this be async_call_with_retry?
        model      = MODEL,
        max_tokens = MAX_OUTPUT,
        system     = system,
        messages   = messages,
    )

    text = response.content[0].text if response.content else ""
    usage = calculate_cost(response.usage.input_tokens, response.usage.output_tokens)

    return {"content": text, "usage": usage}


# ── 7. Streaming Chat ──────────────────────────────────────────────────────────

def chat_stream(
    messages:      list[dict],
    context_items: list[dict] | None = None,
) -> Iterator[str]:
    """
    Stream a chat response as SSE-formatted chunks.

    Yields:
        - "data: {token}\\n\\n"  for each text token
        - "data: [DONE]\\n\\n"   followed by
          "data: {usage_json}\\n\\n"  with the final usage/cost object

    Designed for FastAPI StreamingResponse with media_type="text/event-stream".

    Example (FastAPI):
        from fastapi.responses import StreamingResponse

        @app.post("/api/chat")
        def chat(req: ChatRequest):
            return StreamingResponse(
                chat_stream(req.messages, req.context_items),
                media_type="text/event-stream",
            )
    """
    system = build_system_prompt(context_items or [])

    with stream_with_retry(
        model      = MODEL,
        max_tokens = MAX_OUTPUT,
        system     = system,
        messages   = messages,
    ) as stream:
        for text in stream.text_stream:
            yield f"data: {json.dumps(text)}\n\n"

        final  = stream.get_final_message()
        usage  = calculate_cost(final.usage.input_tokens, final.usage.output_tokens)

    yield "data: [DONE]\n\n"
    yield f"data: {json.dumps({'usage': usage})}\n\n"
