"""
Knowledge-base loader and Claude analysis engine for the live call co-pilot.

Uses Anthropic tool use for structured output — Claude is forced to return
valid JSON matching the schema. Non-streaming: returns the complete result.

Provides:
    load_knowledge_base()                    - reads .md files from dummy_data/notes/
    format_knowledge_base(kb)                - formats KB dict into a system-prompt string
    copilot_analyze(transcript, kb_context)  - calls Claude Haiku, returns parsed dict
"""

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ENGINE_DIR = Path(__file__).parent
ROOT_DIR = ENGINE_DIR.parent
NOTES_DIR = ROOT_DIR / "dummy_data" / "notes"

for _p in (ROOT_DIR / "services", ROOT_DIR / "utils"):
    _str = str(_p)
    if _str not in sys.path:
        sys.path.insert(0, _str)

from anthropic_client import call_with_retry, extract_tool_use  # noqa: E402

log = logging.getLogger("copilot.engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """\
You are a real-time meeting co-pilot for a sales consulting team. Your job is to \
detect questions or information requests from anyone on the call and provide \
answers from the knowledge base below.

IMPORTANT: The transcript comes from live speech-to-text and may contain \
misspellings, missing punctuation, or garbled words. Interpret generously — \
if someone seems to be asking something (even without a question mark), treat \
it as a question. Look for phrases like "I want to know", "how do we", \
"what about", "can you tell me", "I'm wondering", etc.

The transcript may be split into two sections:
- [PRIOR CONTEXT] — background from earlier in the call. Use this for context \
only. Do NOT detect questions from this section.
- [NEW SECTION] — the latest portion. Detect questions ONLY from this section.
If there are no section markers, treat the entire transcript as new.

RULES:
- Detect questions and information requests ONLY from the [NEW SECTION].
- Use the [PRIOR CONTEXT] to better understand what is being discussed.
- Answer each in 2-3 sentences max, using ONLY the knowledge base.
- If a topic is not covered in the KB, say so directly in the answer.
- If genuinely no questions or requests are found, return an empty questions array.
- confidence: "high" = directly stated in KB, "medium" = implied, "low" = inferred.
- source: just the filename, e.g. "project-overview.md"

You MUST call the report_questions tool with your findings. Always call it, even \
if the questions array is empty."""

TOOL_SCHEMA = {
    "name": "report_questions",
    "description": "Report detected client questions with answers from the knowledge base.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question or information request detected.",
                        },
                        "answer": {
                            "type": "string",
                            "description": "2-3 sentence answer from the knowledge base only.",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "source": {
                            "type": "string",
                            "description": "Source filename, e.g. 'project-overview.md'.",
                        },
                    },
                    "required": ["question", "answer", "confidence", "source"],
                },
            },
        },
        "required": ["questions"],
    },
}


# ---------------------------------------------------------------------------
# Knowledge-base helpers
# ---------------------------------------------------------------------------
def load_knowledge_base() -> dict[str, str]:
    """Read every .md file under dummy_data/notes/ and return {rel_path: content}."""
    try:
        if not NOTES_DIR.is_dir():
            log.warning("Notes directory not found: %s", NOTES_DIR)
            return {}

        kb: dict[str, str] = {}
        for md_path in sorted(NOTES_DIR.rglob("*.md")):
            if md_path.name.startswith("._"):
                continue
            rel = str(md_path.relative_to(NOTES_DIR))
            try:
                kb[rel] = md_path.read_text(encoding="utf-8")
            except OSError as exc:
                log.error("Failed to read KB file %s: %s", md_path, exc)
        return kb
    except Exception as exc:
        log.exception("Failed to load knowledge base: %s", exc)
        raise


def format_knowledge_base(kb: dict[str, str]) -> str:
    """Flatten the KB dict into a single string for the system prompt."""
    try:
        if not kb:
            return "(no knowledge-base documents loaded)"
        sections: list[str] = []
        for rel_path, content in kb.items():
            sections.append(f"### {rel_path}\n{content}")
        return "\n\n".join(sections)
    except Exception as exc:
        log.exception("Failed to format knowledge base: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Analysis engine — non-streaming tool use
# ---------------------------------------------------------------------------
def copilot_analyze(transcript: str, kb_context: str) -> dict:
    """
    Call Claude Haiku with tool use to detect and answer questions.

    Returns dict: {"questions": [...]} on success,
                  {"questions": [], "error": "..."} on failure.
    """
    system_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- KNOWLEDGE BASE ---\n{kb_context}\n--- END KNOWLEDGE BASE ---"
    )

    try:
        response = call_with_retry(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": transcript}],
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "report_questions"},
        )
    except Exception as exc:
        log.exception("Claude API call failed: %s", exc)
        return {"questions": [], "error": f"Claude API error: {exc}"}

    try:
        tool_block = extract_tool_use(response)
        if tool_block is None:
            log.error("No tool_use block in Claude response: %s", response)
            return {"questions": [], "error": "Claude did not return a tool call"}
        return tool_block.input
    except Exception as exc:
        log.exception("Failed to extract tool result: %s", exc)
        return {"questions": [], "error": f"Result extraction error: {exc}"}
