# Phase 2: Apply Edit Logic (Python port of apply-edits.js)
#
# Takes proposed edits from the extraction phase and applies them to project files.
# Follows Claude Code's FileEditTool patterns for correctness and safety.
#
# Design decisions — see docs/phase-2-apply.md for full rationale.
#
# NOTE: read_file_state is module-level mutable state. Safe with a single uvicorn
# worker (asyncio is single-threaded). Do NOT run with --workers N > 1 without
# moving this to a request-scoped store.

import re
import subprocess
from pathlib import Path

import regex  # PyPI 'regex' package — needed for \p{L} Unicode property escapes
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

# ---------------------------------------------------------------------------
# Read-state tracking
# Mirrors Claude Code's readFileState map.
# Maps absolute path string → { "content": str, "mtime": float }
# Every file must be read (and tracked here) before it can be edited.
# ---------------------------------------------------------------------------
read_file_state: dict[str, dict] = {}


def track_read(absolute_path: str) -> str:
    p = Path(absolute_path)
    content = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    mtime = p.stat().st_mtime
    read_file_state[absolute_path] = {"content": content, "mtime": mtime}
    return content


def load_project_files(project_dir: str) -> dict[str, str]:
    files = {}
    base = Path(project_dir)
    for full in base.rglob("*.md"):
        rel = str(full.relative_to(base))
        files[rel] = track_read(str(full))
    return files


# ---------------------------------------------------------------------------
# Quote normalization (copied from Claude Code FileEditTool/utils.ts)
# Claude sometimes outputs curly quotes when the file has straight quotes.
# Normalize both sides before matching so edits don't silently fail.
# ---------------------------------------------------------------------------
def normalize_quotes(s: str) -> str:
    return (
        s.replace("\u2018", "'").replace("\u2019", "'")   # curly single ' '
         .replace("\u201c", '"').replace("\u201d", '"')   # curly double " "
    )


def find_actual_string(file_content: str, search_string: str) -> str | None:
    if search_string in file_content:
        return search_string

    # Try with normalized quotes
    normalized_search = normalize_quotes(search_string)
    normalized_file = normalize_quotes(file_content)
    idx = normalized_file.find(normalized_search)
    if idx != -1:
        return file_content[idx : idx + len(search_string)]

    return None


def preserve_quote_style(old_value: str, actual_old_value: str, new_value: str) -> str:
    if old_value == actual_old_value:
        return new_value

    has_curly_double = bool(re.search(r'[\u201c\u201d]', actual_old_value))
    has_curly_single = bool(re.search(r'[\u2018\u2019]', actual_old_value))

    result = new_value

    if has_curly_double:
        def replace_double(m):
            offset = m.start()
            prev = result[offset - 1] if offset > 0 else ''
            is_opening = not prev or re.match(r'[\s(\[{]', prev)
            return '\u201c' if is_opening else '\u201d'
        result = re.sub(r'"', replace_double, result)

    if has_curly_single:
        def replace_single(m):
            s = result
            offset = m.start()
            prev = s[offset - 1] if offset > 0 else ''
            nxt  = s[offset + 1] if offset + 1 < len(s) else ''
            # apostrophe between letters
            if regex.match(r'\p{L}', prev) and regex.match(r'\p{L}', nxt):
                return '\u2019'
            return '\u2018' if (re.match(r'[\s(\[{]', prev) or not prev) else '\u2019'
        result = re.sub(r"'", replace_single, result)

    return result


# ---------------------------------------------------------------------------
# clarify_old_value — called when old_value is not found or is ambiguous.
# Uses Haiku (sufficient for this task) with the full transcript for context.
# new_value is never passed to Claude — we keep the original throughout.
# ---------------------------------------------------------------------------
async def clarify_old_value(content: str, edit: dict, error: str, transcript: str) -> str | None:
    problem = (
        "The old_value you chose appears more than once in the file, so it's ambiguous which occurrence to replace."
        if error == "AMBIGUOUS_MATCH"
        else "The old_value you chose was not found verbatim in the file. It may have been slightly paraphrased or misquoted."
    )

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""You are maintaining a set of markdown files that get updated as new information comes in.
The way edits work is: you choose an old_value (exact text currently in the file) and
a new_value (what replaces it). This is a find-and-replace — old_value must exist
verbatim and exactly once in the file.

You proposed this edit:

  old_value: "{edit['old_value']}"
  new_value: "{edit['new_value']}"

Problem: {problem}

Here is the transcript you were working from:
---
{transcript}
---

Here is the current file content:
---
{content}
---

Please choose a revised old_value that exists verbatim and exactly once in the file
above, and still correctly identifies the text you intended to replace.
The new_value does not change — only old_value needs to be fixed."""
        }],
        tools=[{
            "name": "revised_old_value",
            "description": "Return only the corrected old_value",
            "input_schema": {
                "type": "object",
                "properties": {
                    "old_value": {"type": "string"}
                },
                "required": ["old_value"]
            }
        }],
        tool_choice={"type": "tool", "name": "revised_old_value"}
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        return None

    revised = tool_use.input["old_value"]

    # Sanity check: must exist exactly once
    first = content.find(revised)
    if first == -1:
        return None
    if content.find(revised, first + 1) != -1:
        return None

    return revised


# ---------------------------------------------------------------------------
# apply_edit_to_content — pure function, no I/O
# Applies one edit to a string and returns the updated string.
# Handles trailing-newline cleanup when new_value is empty (deletion).
#
# IMPORTANT: str.replace(old, new, 1) — the count=1 is mandatory.
# JS String.replace(literal) only replaces the first occurrence;
# Python's str.replace() replaces all by default.
# ---------------------------------------------------------------------------
def apply_edit_to_content(content: str, actual_old_value: str, actual_new_value: str) -> str:
    if actual_new_value != "":
        return content.replace(actual_old_value, actual_new_value, 1)
    # Deletion: strip the trailing newline too so we don't leave a blank line
    if not actual_old_value.endswith("\n") and (actual_old_value + "\n") in content:
        return content.replace(actual_old_value + "\n", "", 1)
    return content.replace(actual_old_value, "", 1)


# ---------------------------------------------------------------------------
# apply_single_edit — applies one edit to the running content in memory.
# Retries once via clarify_old_value on NOT_FOUND or AMBIGUOUS.
# Returns dict with keys: success, content (on success), error, edit
# ---------------------------------------------------------------------------
async def apply_single_edit(
    current_content: str,
    edit: dict,
    transcript: str,
    retrying: bool = False,
    skip_retry: bool = False,
) -> dict:
    actual_old_value = find_actual_string(current_content, edit["old_value"])

    if not actual_old_value:
        if retrying or skip_retry:
            return {"success": False, "error": "OLD_VALUE_NOT_FOUND", "edit": edit}
        revised = await clarify_old_value(current_content, edit, "OLD_VALUE_NOT_FOUND", transcript)
        if not revised:
            return {"success": False, "error": "OLD_VALUE_NOT_FOUND", "edit": edit}
        return await apply_single_edit(
            current_content, {**edit, "old_value": revised}, transcript, retrying=True, skip_retry=skip_retry
        )

    match_count = current_content.count(actual_old_value)
    if match_count > 1:
        if retrying or skip_retry:
            return {"success": False, "error": "AMBIGUOUS_MATCH", "count": match_count, "edit": edit}
        revised = await clarify_old_value(current_content, edit, "AMBIGUOUS_MATCH", transcript)
        if not revised:
            return {"success": False, "error": "AMBIGUOUS_MATCH", "edit": edit}
        return await apply_single_edit(
            current_content, {**edit, "old_value": revised}, transcript, retrying=True, skip_retry=skip_retry
        )

    actual_new_value = preserve_quote_style(edit["old_value"], actual_old_value, edit["new_value"])
    updated_content = apply_edit_to_content(current_content, actual_old_value, actual_new_value)

    if updated_content == current_content:
        return {"success": False, "error": "NO_CHANGE", "edit": edit}

    return {"success": True, "content": updated_content, "edit": edit}


# ---------------------------------------------------------------------------
# apply_batch — applies a full set of proposed edits to project files.
#
# Flow:
#   1. Load all project files into read_file_state
#   2. Group edits by file_path
#   3. Per file: apply edits sequentially against running in-memory state
#      — check old_value ⊄ previous new_value (Claude Code multi-edit safety)
#   4. Hold all updates in memory — write nothing yet
#   5. Staleness check (mtime) immediately before write
#   6. Write all files synchronously — no awaits between read and write
#   7. Git commit
#
# Returns dict: { applied, failed, skipped, commit_hash }
# ---------------------------------------------------------------------------
async def apply_batch(
    proposed_edits: list[dict],
    project_dir: str,
    transcript: str,
    transcript_name: str,
    options: dict | None = None,
) -> dict:
    skip_retry = (options or {}).get("skip_retry", False)

    # 1. Load all files
    project_files = load_project_files(project_dir)
    known_paths = set(project_files.keys())

    # Separate valid edits from hallucinated file paths upfront
    valid_edits = []
    skipped = []
    for edit in proposed_edits:
        if edit["file_path"] not in known_paths:
            skipped.append({"edit": edit, "reason": "UNKNOWN_FILE_PATH"})
        else:
            valid_edits.append(edit)

    # 2. Group by file
    by_file: dict[str, list] = {}
    for edit in valid_edits:
        by_file.setdefault(edit["file_path"], []).append(edit)

    # 3. Apply edits per file, in memory
    pending_writes: dict[str, str] = {}   # absolute path → updated content
    applied = []
    failed = []

    for rel_path, edits in by_file.items():
        absolute_path = str(Path(project_dir) / rel_path)
        running_content = read_file_state[absolute_path]["content"]
        applied_new_values = []

        for edit in edits:
            # Claude Code multi-edit safety: old_value must not be ⊂ a previous new_value
            if any(
                edit["old_value"] != "" and prev.find(edit["old_value"]) != -1
                for prev in applied_new_values
            ):
                failed.append({"edit": edit, "error": "OLD_VALUE_SUBSET_OF_PREVIOUS_NEW_VALUE"})
                continue

            result = await apply_single_edit(running_content, edit, transcript, skip_retry=skip_retry)
            if result["success"]:
                running_content = result["content"]
                applied_new_values.append(edit["new_value"])
                applied.append({"edit": edit, "file": rel_path})
            else:
                failed.append({"edit": edit, "error": result["error"]})

        if running_content != read_file_state[absolute_path]["content"]:
            pending_writes[absolute_path] = running_content

    # 4 + 5 + 6. Staleness check + synchronous write — no awaits in this block
    commit_hash = None
    if pending_writes:
        for absolute_path in list(pending_writes.keys()):
            state = read_file_state[absolute_path]
            current_mtime = Path(absolute_path).stat().st_mtime
            if current_mtime > state["mtime"]:
                # File changed on disk since we read it — abort this file
                rel = str(Path(absolute_path).relative_to(project_dir))
                failed.append({"file": rel, "error": "FILE_MODIFIED_SINCE_READ"})
                del pending_writes[absolute_path]

        # Synchronous writes — no awaits between reads and writes (atomicity)
        for absolute_path, updated_content in pending_writes.items():
            Path(absolute_path).write_text(updated_content, encoding="utf-8")
            new_mtime = Path(absolute_path).stat().st_mtime
            read_file_state[absolute_path] = {"content": updated_content, "mtime": new_mtime}

        # 7. Git commit
        try:
            files_arg = [str(p) for p in pending_writes.keys()]
            subprocess.run(
                ["git", "-C", project_dir, "add"] + files_arg,
                capture_output=True, check=True
            )
            msg = f"call: {transcript_name} — {len(applied)} edit{'s' if len(applied) != 1 else ''} applied"
            subprocess.run(
                ["git", "-C", project_dir, "commit", "-m", msg],
                capture_output=True, check=True
            )
            result = subprocess.run(
                ["git", "-C", project_dir, "rev-parse", "--short", "HEAD"],
                capture_output=True, check=True
            )
            commit_hash = result.stdout.decode().strip()
        except subprocess.CalledProcessError as e:
            # Git not available or no changes to commit — non-fatal
            print(f"  git commit skipped: {e.stderr.decode().split(chr(10))[0]}")

    return {"applied": applied, "failed": failed, "skipped": skipped, "commit_hash": commit_hash}


__all__ = ["apply_batch", "load_project_files", "track_read"]
