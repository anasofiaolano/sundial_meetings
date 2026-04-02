# Inngest functions for Sundial CRM
#
# Handles async transcript extraction as a 4-step durable function:
#   Step 1: count-tokens    — validates token budget (fast, retryable)
#   Step 2: claude-extract  — calls Claude sonnet (expensive, memoized on retry)
#   Step 3: validate-edits  — checks old_values against live files
#   Step 4: save-call       — writes edits to calls.json, status → "pending"
#
# On failure after all retries: on_failure handler sets status → "failed".
#
# Steps are memoized by Inngest — if a retry occurs, only the failing step
# re-runs. Earlier steps (including the Claude call) are replayed from
# Inngest's log without re-executing, so retries don't re-spend API credits.

import json
from datetime import datetime, timezone
from pathlib import Path

import inngest
from anthropic import AsyncAnthropic
from logging_config import get_logger

log = get_logger("inngest_functions")

# ── Constants (mirrors server.py) ────────────────────────────────────────────

BASE_DIR    = Path(__file__).parent
PROJECT_DIR = BASE_DIR / "test-data" / "golden-eagle"
CALLS_LOG   = BASE_DIR / "test-data" / "calls.json"

SYSTEM_PROMPT = """You are an expert sales data analyst for a consulting firm. Your job is to read a call transcript and propose targeted updates to the engagement's project files. You propose only — the consultant reviews and accepts.

## Context
These files track a consulting engagement. They are completely free-form markdown — no fixed structure, no required fields. Each file evolves naturally based on what comes up in calls.

## How edits work
Every edit is a find-and-replace: old_value is the exact text currently in the file, new_value is what replaces it. This covers everything:
- Replacing a placeholder: old_value = "(no notes yet)", new_value = actual content
- Updating a fact: old_value = old sentence/paragraph, new_value = corrected version
- Augmenting: old_value = existing paragraph, new_value = same paragraph with new sentences added
- Adding a section: old_value = last line of file, new_value = that line + new section below it

The files are the ground truth. You have been given their full content above — your old_value MUST come verbatim from that content. If you cannot find the exact text you want to replace, do not propose the edit.

## Rules
1. Only propose edits for facts EXPLICITLY stated in the call — not implied or inferred.
2. If the information is already captured in the file, do not re-propose it.
3. old_value must be copied verbatim from the file content provided. No paraphrasing.
4. For each edit, quote the exact sentence or phrase from the transcript that justifies it.
5. If you are unsure, do not propose.
6. Let the content determine its own structure — add sections, prose, bullet points, whatever fits naturally.
7. If a transcript contains no new facts about the client engagement, return []."""

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path":    {"type": "string"},
                    "field_label":  {"type": "string"},
                    "old_value":    {"type": "string"},
                    "new_value":    {"type": "string"},
                    "confidence":   {"type": "string", "enum": ["high", "medium", "low"]},
                    "source_quote": {"type": "string"},
                },
                "required": ["file_path", "field_label", "old_value", "new_value", "confidence", "source_quote"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["edits"],
}

TOKEN_LIMIT = 160_000

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_calls_log() -> list:
    if not CALLS_LOG.exists():
        return []
    return json.loads(CALLS_LOG.read_text(encoding="utf-8"))

def save_calls_log(calls: list) -> None:
    CALLS_LOG.write_text(json.dumps(calls, indent=2), encoding="utf-8")

def load_project_files() -> dict[str, str]:
    files = {}
    for full in PROJECT_DIR.rglob("*.md"):
        rel = str(full.relative_to(PROJECT_DIR))
        files[rel] = full.read_text(encoding="utf-8")
    return files

def build_user_message(transcript: str) -> str:
    project_files = load_project_files()
    file_context = "\n\n---\n\n".join(
        f"[FILE: {rel}]\n{content}" for rel, content in project_files.items()
    )
    return f"## Call Transcript\n{transcript}\n\n---\n\n## Current Project Files\n{file_context}"

# ── Inngest client ────────────────────────────────────────────────────────────

inngest_client = inngest.Inngest(app_id="sundial", is_production=False)

# ── Failure handler ───────────────────────────────────────────────────────────

async def handle_extract_failure(ctx: inngest.Context) -> None:
    """Called by Inngest after all retries are exhausted. Marks the call as failed."""
    call_id = ctx.event.data.get("call_id")
    error   = str(ctx.event.data.get("error", {}).get("message", "unknown error"))
    if not call_id:
        return
    calls = load_calls_log()
    call  = next((c for c in calls if c["id"] == call_id), None)
    if call:
        call["status"]    = "failed"
        call["failed_at"] = datetime.now(timezone.utc).isoformat()
        call["error"]     = error
        save_calls_log(calls)
    log.error("EXTRACTION PERMANENTLY FAILED — callId=%s error=%s", call_id, error)

# ── Main extraction function ──────────────────────────────────────────────────

@inngest_client.create_function(
    fn_id="extract-transcript",
    trigger=inngest.TriggerEvent(event="sundial/extract.requested"),
    retries=3,
    on_failure=handle_extract_failure,
)
async def extract_transcript(ctx: inngest.Context) -> dict:
    step       = ctx.step
    data       = ctx.event.data
    call_id    = data["call_id"]
    transcript = data["transcript"]
    log.info("extract_transcript START — callId=%s transcript_len=%d", call_id, len(transcript))

    # ── Step 1: count tokens ────────────────────────────────────────────────
    # Raises NonRetriableError if transcript is too large — no point retrying.
    async def count_tokens() -> dict:
        client = AsyncAnthropic()
        user_message = build_user_message(transcript)
        messages = [{"role": "user", "content": user_message}]
        count = await client.messages.count_tokens(
            model="claude-sonnet-4-6", system=SYSTEM_PROMPT, messages=messages
        )
        if count.input_tokens > TOKEN_LIMIT:
            log.error("TOKEN_LIMIT_EXCEEDED — callId=%s tokens=%d limit=%d",
                      call_id, count.input_tokens, TOKEN_LIMIT)
            raise inngest.NonRetriableError(
                f"Token budget exceeded: {count.input_tokens:,} (limit {TOKEN_LIMIT:,})"
            )
        log.info("token count OK — callId=%s tokens=%d", call_id, count.input_tokens)
        return {"token_count": count.input_tokens, "user_message": user_message}

    token_result = await step.run("count-tokens", count_tokens)
    log.info("step count-tokens complete — callId=%s", call_id)

    # ── Step 2: call Claude extraction ─────────────────────────────────────
    # Memoized on retry — if this step succeeds, subsequent retries skip it
    # and replay the result, so Claude is not called again.
    async def claude_extract() -> list:
        client = AsyncAnthropic()
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": token_result["user_message"]}],
            tools=[{
                "name": "propose_edits",
                "description": "Output the proposed edits array",
                "input_schema": TOOL_SCHEMA,
            }],
            tool_choice={"type": "tool", "name": "propose_edits"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            log.error("NO_TOOL_USE_BLOCK in Claude response — callId=%s", call_id)
            raise ValueError("No tool_use block in Claude response")
        edits = tool_use.input.get("edits", [])
        log.info("Claude extracted %d raw edits — callId=%s", len(edits), call_id)
        return edits

    raw_edits = await step.run("claude-extract", claude_extract)
    log.info("step claude-extract complete — callId=%s raw_edits=%d", call_id, len(raw_edits))

    # ── Step 3: validate edits against live file content ────────────────────
    async def validate_edits() -> list:
        project_files = load_project_files()
        known_paths   = set(project_files.keys())
        return [
            {
                **edit,
                "_valid": (
                    edit["file_path"] in known_paths
                    and edit["old_value"] in project_files.get(edit["file_path"], "")
                ),
                "_error": (
                    "hallucinated_path" if edit["file_path"] not in known_paths
                    else "old_value_not_found" if edit["old_value"] not in project_files.get(edit["file_path"], "")
                    else None
                ),
            }
            for edit in raw_edits
        ]

    edits = await step.run("validate-edits", validate_edits)

    # ── Step 4: update calls.json → "pending" ──────────────────────────────
    async def save_call() -> dict:
        calls = load_calls_log()
        call  = next((c for c in calls if c["id"] == call_id), None)
        if call:
            call["status"]      = "pending"
            call["edits"]       = edits
            call["token_count"] = token_result["token_count"]
            save_calls_log(calls)
        return {"ok": True, "edit_count": len(edits)}

    result = await step.run("save-call", save_call)
    log.info("extract_transcript DONE — callId=%s edits=%d status=pending", call_id, result["edit_count"])
    return {"call_id": call_id, "edit_count": result["edit_count"]}
