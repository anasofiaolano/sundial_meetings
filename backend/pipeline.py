# pipeline.py
#
# Step-by-step pipeline for one transcript.
# Saves state after each step so it can resume if interrupted.
#
# Philosophy: each step checks if it already ran (saved to disk).
# If yes — skip it. If no — run it and save. Re-running is always safe.
#
# Steps:
#   1. read_transcript  — load and copy the .txt file into the run folder
#   2. extract          — Claude proposes field-level edits to notes files
#   3. apply_edits      — apply the proposed edits and commit to git
#   4. write_summary    — write a human-readable summary.md
#   5. briefing         — generate a post-call briefing (6 Claude calls)
#   6. email_html       — render a styled HTML email summary from the briefing (no Claude)
#
# Usage (standalone):
#   python pipeline.py <transcript_path> [--name <name>] [--project-dir <dir>]
#
# Usage (from worker):
#   from pipeline import run_pipeline
#   await run_pipeline(transcript_path, transcript_name, project_dir)

import asyncio
import json
import logging
import sys
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
# Build absolute paths relative to this file so the script works regardless of
# the working directory it's launched from.
BASE_DIR   = Path(__file__).parent          # backend/
ROOT_DIR   = BASE_DIR.parent                # repo root (sundial_meetings_AO/)
UTILS_DIR  = ROOT_DIR / "utils"             # shared utilities (time_utils, etc.)
NOTES_DIR  = ROOT_DIR / "dummy_data" / "notes"  # default project files directory
RUNS_DIR   = BASE_DIR / "runs"              # one subfolder per run: runs/<id>-<name>/

# Phase modules (extract, apply_edits, email_html) live in the sibling repo.
# briefing.py lives in pipeline/backend/ within this repo.
_SIBLING   = ROOT_DIR.parent / "sundial_meetings"   # ../sundial_meetings/
PHASE1_DIR = _SIBLING / "phase-1-extract"
PHASE2_DIR = _SIBLING / "phase-2-apply"
PHASE5_DIR = ROOT_DIR / "pipeline" / "backend"      # briefing.py is here
PHASE6_DIR = _SIBLING / "phase-6-email"

# Add all to sys.path so imports resolve without installing packages.
for p in (UTILS_DIR, PHASE1_DIR, PHASE2_DIR, PHASE5_DIR, PHASE6_DIR):
    if p.exists():
        sys.path.insert(0, str(p))

from extract import extract          # noqa: E402 — phase-1: calls Claude to propose edits
from apply_edits import apply_batch  # noqa: E402 — phase-2: applies proposed edits to notes files
from time_utils import now_pt, now_pt_tag  # noqa: E402 — Pacific-time helpers
from briefing import generate_briefing      # noqa: E402 — phase-5: post-call briefing
from email_html import generate_email_html  # noqa: E402 — phase-6: HTML email summary


# ---------------------------------------------------------------------------
# Per-run log helpers
# ---------------------------------------------------------------------------
# Each run gets its own run.log inside its run_dir. We attach a FileHandler to
# the named loggers used by each module so all their output flows into that
# file for the duration of the run, then detach when done.
# This lets you open runs/<id>-<name>/run.log and see exactly what happened.

# Names of the Python loggers captured into the per-run log file.
# "pipeline" is defined below; others are defined in their own modules.
_RUN_LOGGERS = ("pipeline", "extract", "apply_edits", "briefing", "email_html")

# Pipeline-level logger — step progress, skip decisions, and counts go here.
log = logging.getLogger("pipeline")


def _attach_run_handler(run_dir: Path) -> logging.FileHandler:
    """
    Open run_dir/run.log for writing and attach it to each of the module
    loggers in _RUN_LOGGERS. Returns the handler so the caller can detach it later.
    """
    # FileHandler opens (or creates) the log file in append mode by default.
    handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    # DEBUG captures everything — INFO, WARNING, ERROR, and CRITICAL too.
    handler.setLevel(logging.DEBUG)
    # Each line: timestamp  logger-name  level  message
    handler.setFormatter(logging.Formatter("%(asctime)s  %(name)s  %(levelname)s  %(message)s"))
    # Attach the same handler to all loggers so their output is interleaved
    # chronologically in a single file.
    for name in _RUN_LOGGERS:
        logging.getLogger(name).addHandler(handler)
    return handler


def _detach_run_handler(handler: logging.FileHandler):
    """
    Remove the handler from all captured loggers and close the file.
    Called in a finally block so it always runs even if the pipeline crashes.
    Without this, the handler would linger on the global logger and the next
    run would accidentally write into this run's log file.
    """
    for name in _RUN_LOGGERS:
        logging.getLogger(name).removeHandler(handler)
    handler.close()  # flushes any buffered output and releases the file descriptor


# ---------------------------------------------------------------------------
# Step state helpers
# ---------------------------------------------------------------------------
# State is stored in runs/<id>-<name>/state.json as a dict of step → result.
# Each step is "done" or absent. Absent means it hasn't run yet.
# This is how the pipeline can resume mid-run after a crash or interruption.

def _state_file(run_dir: Path) -> Path:
    return run_dir / "state.json"


def _load_state(run_dir: Path) -> dict:
    """Load existing state from disk, or return an empty state if this is a fresh run."""
    f = _state_file(run_dir)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"steps": {}}


def _save_state(run_dir: Path, state: dict):
    """Persist the current state dict to disk."""
    _state_file(run_dir).write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _is_done(state: dict, step: str) -> bool:
    """Return True if this step already completed successfully in a prior run."""
    return state["steps"].get(step, {}).get("status") == "done"


def _get_result(state: dict, step: str):
    """Retrieve the saved result payload for a completed step."""
    return state["steps"][step].get("result")


def _mark_done(run_dir: Path, state: dict, step: str, result=None):
    """
    Record a step as done with its result and the completion timestamp,
    then immediately save state to disk so it survives a crash.
    """
    state["steps"][step] = {
        "status":       "done",
        "completed_at": now_pt(),  # Pacific time — human-readable in the JSON file
        "result":       result,
    }
    _save_state(run_dir, state)
    print(f"  ✓  {step}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _fetch_session_notes(job_id: str) -> str | None:
    """
    Look up rep notes linked to this job (via call_sessions.job_id).
    Returns a formatted string of non-private notes, or None if no session found.
    Private notes are excluded — they never leave the session view.
    """
    import sqlite3 as _sqlite3
    try:
        conn = _sqlite3.connect(BASE_DIR / "jobs.db", isolation_level=None)
        conn.row_factory = _sqlite3.Row
        session = conn.execute(
            "SELECT id FROM call_sessions WHERE job_id = ? LIMIT 1", (job_id,)
        ).fetchone()
        if not session:
            conn.close()
            return None
        rows = conn.execute(
            """SELECT text, type, is_bookmark FROM call_notes
               WHERE session_id = ? AND type != 'private'
               ORDER BY position, created_at""",
            (session["id"],),
        ).fetchall()
        conn.close()
        if not rows:
            return None

        TYPE_LABEL = {
            "note":       "Note",
            "action":     "Action item",
            "question":   "Question",
            "commitment": "They committed to",
        }
        lines = ["## Rep's notes from this call"]
        for row in rows:
            if row["is_bookmark"]:
                lines.append(f"[Bookmark] {row['text']}")
            else:
                label = TYPE_LABEL.get(row["type"], "Note")
                lines.append(f"[{label}] {row['text']}")
        return "\n".join(lines)
    except Exception:
        log.warning("_fetch_session_notes failed for job_id=%s", job_id, exc_info=True)
        return None


async def run_pipeline(
    transcript_path: str,
    transcript_name: str,
    project_dir: str = str(NOTES_DIR),
    job_id: str | None = None,
    focus_hint: str | None = None,
    run_briefing: bool = True,  # False for reruns — skip step 5
    run_dir: str | None = None, # existing run folder path from DB — skip folder scan
) -> dict:
    """
    Run the transcript pipeline with per-step checkpointing.
    Returns the final result dict.
    Re-running resumes from the last completed step.

    run_dir is keyed by job_id (if provided) so two jobs with the same
    transcript_name never share checkpoint state.
    """
    # Run folder format: YYYYMMDDHHMMSS-{name}
    # - datetime prefix: folders sort chronologically in the filesystem
    # - name: human-readable at a glance
    # - UUID is NOT in the folder name — run_dir is stored as a DB column
    #   and passed in by the worker. No filesystem scanning needed.
    if run_dir:
        run_dir = Path(run_dir)
    else:
        run_dir = RUNS_DIR / f"{now_pt_tag()}-{transcript_name}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Load any checkpointed step results from a previous (interrupted) run.
    state = _load_state(run_dir)

    print(f"\n{'─' * 60}")
    print(f"  {transcript_name}")
    print(f"  {run_dir}")
    print(f"{'─' * 60}")

    # Attach the per-run file logger before any steps run so all log output
    # from all modules is captured in run_dir/run.log.
    log_handler = _attach_run_handler(run_dir)
    try:
        return await _run_steps(
            run_dir, state, transcript_path, transcript_name, project_dir, focus_hint, run_briefing,
            job_id=job_id,
        )
    except Exception:
        # Log the full traceback to run.log so it's visible even without a terminal.
        log.exception("pipeline crashed")
        raise
    finally:
        # Always detach — success or exception — to keep the global logger clean.
        _detach_run_handler(log_handler)


async def _run_steps(
    run_dir: Path,
    state: dict,
    transcript_path: str,
    transcript_name: str,
    project_dir: str,
    focus_hint: str | None,
    run_briefing: bool = True,
    job_id: str | None = None,
) -> dict:
    # ── Step 1: read transcript ──────────────────────────────────────────────
    # Just reads the .txt file and saves a copy inside the run folder.
    # The copy is what later steps (and the GUI) read — it's stable even if the
    # original file moves or is deleted.
    if _is_done(state, "read_transcript"):
        print("  ↩  read_transcript (skipping)")
        log.info("read_transcript — skipping (already done)")
        transcript_text = (run_dir / "transcript.txt").read_text(encoding="utf-8")
    else:
        print("  ▶  read_transcript ...")
        log.info("read_transcript — starting, path=%s", transcript_path)
        try:
            transcript_text = Path(transcript_path).read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ✗  read_transcript failed: {e}")
            log.exception("read_transcript FAILED — path=%s", transcript_path)
            raise
        (run_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")
        log.info("read_transcript — done (%d chars)", len(transcript_text))
        _mark_done(run_dir, state, "read_transcript")

    # ── Step 2: extract ──────────────────────────────────────────────────────
    # Calls Claude with the transcript + all project files. Claude returns a list
    # of proposed edits (field-level updates). Each edit is validated and tagged
    # with _valid=True/False. Invalid edits are kept in the JSON for debugging
    # but filtered out before apply.
    if _is_done(state, "extract"):
        print("  ↩  extract (skipping)")
        log.info("extract — skipping (already done)")
        cached = _get_result(state, "extract")
        edits, tokens, reasoning = cached["edits"], cached["tokens"], cached.get("reasoning", "")
    else:
        print("  ▶  extract (calling Claude) ...")
        log.info("extract — starting")
        edits, tokens, reasoning = extract(transcript_text, Path(project_dir), focus_hint=focus_hint)
        valid   = sum(1 for e in edits if e.get("_valid"))
        invalid = len(edits) - valid
        print(f"       {tokens:,} tokens · {len(edits)} proposed · {valid} valid · {invalid} invalid")
        log.info("extract — done: %d tokens · %d proposed · %d valid · %d invalid",
                 tokens, len(edits), valid, invalid)
        # Print reasoning so it's visible in the worker terminal output.
        if reasoning:
            print(f"       reasoning: {reasoning}")

        # Save the full extract output to disk for inspection / debugging.
        # reasoning is included so it's visible in extract.json alongside the edits.
        (run_dir / "extract.json").write_text(
            json.dumps({"tokens": tokens, "reasoning": reasoning, "edits": edits}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _mark_done(run_dir, state, "extract", result={"tokens": tokens, "reasoning": reasoning, "edits": edits})

    # Only pass valid edits to the apply step.
    valid_edits = [e for e in edits if e.get("_valid")]

    # ── Step 3: apply edits ──────────────────────────────────────────────────
    # Writes each proposed edit into the appropriate notes file. Each edit is
    # applied by calling Claude (Haiku) to do the actual in-place text surgery,
    # then committed to git. Skipped if there are no valid edits to apply.
    if _is_done(state, "apply_edits"):
        print("  ↩  apply_edits (skipping)")
        log.info("apply_edits — skipping (already done)")
        apply_result = _get_result(state, "apply_edits")
    elif not valid_edits:
        print("  –  apply_edits (no valid edits — skipping)")
        # Log at WARNING so it's prominent in run.log — 0 edits is the most common silent failure.
        log.warning("apply_edits — skipping: 0 valid edits from extract. reasoning: %s",
                    reasoning or "(none)")
        apply_result = {
            "applied": [], "failed": [], "skipped": [],
            "commit_hash": None,
        }
        _mark_done(run_dir, state, "apply_edits", result=apply_result)
    else:
        print(f"  ▶  apply_edits ({len(valid_edits)} edits) ...")
        log.info("apply_edits — starting (%d valid edits)", len(valid_edits))
        apply_result = await apply_batch(
            proposed_edits=valid_edits,
            project_dir=project_dir,
            transcript=transcript_text,
            transcript_name=transcript_name,
        )
        n_applied = len(apply_result.get("applied", []))
        n_failed  = len(apply_result.get("failed", []))
        commit    = apply_result.get("commit_hash") or "none"
        print(f"       {n_applied} applied · {n_failed} failed · commit {commit}")
        log.info("apply_edits — done: %d applied · %d failed · commit %s", n_applied, n_failed, commit)
        if n_failed:
            log.warning("apply_edits — %d edit(s) failed, see apply.json for details", n_failed)

        # Save apply results to disk (applied/failed/skipped + commit hash).
        (run_dir / "apply.json").write_text(
            json.dumps(apply_result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        _mark_done(run_dir, state, "apply_edits", result=apply_result)

    # ── Step 4: write summary ────────────────────────────────────────────────
    # Writes a human-readable summary.md inside the run folder.
    # Re-runs skip this if it's already written.
    if not _is_done(state, "write_summary"):
        print("  ▶  write_summary ...")
        log.info("write_summary — starting")
        _write_summary(run_dir, transcript_name, edits, tokens, apply_result, reasoning)
        log.info("write_summary — done")
        _mark_done(run_dir, state, "write_summary")

    # ── Step 5: briefing ─────────────────────────────────────────────────────
    # Skipped for reruns (run_briefing=False) — reruns are extract+apply only.
    # TODO: revisit this once reruns have a cleaner first-class model. The
    # run_briefing flag is a workaround; ideally the pipeline knows whether a
    # job is a rerun from its own context rather than being told by the worker.
    #
    # Generate a post-call briefing using 6 Claude calls:
    #   step 2 — synthesise engagement context from notes files
    #   steps 3a–3f — one call per section (summary, attendees, topics,
    #                 key_items, action_items, email_draft)
    # Saves briefing.json + briefing.md to the run folder.
    # The JSON string and generated_at timestamp are returned in the result
    # dict so worker.py can store them in the briefing / briefing_at DB columns.
    if not run_briefing:
        print("  –  briefing (skipped — rerun)")
        log.info("briefing — skipped (run_briefing=False)")
        briefing_json_str = "{}"
        briefing_at       = ""
    elif _is_done(state, "briefing"):
        print("  ↩  briefing (skipping)")
        log.info("briefing — skipping (already done)")
        cached_briefing = _get_result(state, "briefing")
        # cached_briefing is stored as the full dict; recover json string from disk
        briefing_json_str = (run_dir / "briefing.json").read_text(encoding="utf-8")
        briefing_at       = cached_briefing.get("generated_at", "")
    else:
        print("  ▶  briefing (calling Claude × 6) ...")
        log.info("briefing — starting")

        # If a call session with rep notes is linked to this job, append the notes
        # to the transcript so Claude can use them as emphasis signals (Granola model).
        # Private notes are excluded — they never leave the session view.
        transcript_for_briefing = transcript_text
        if job_id:
            rep_notes = _fetch_session_notes(job_id)
            if rep_notes:
                transcript_for_briefing = transcript_text + "\n\n" + rep_notes
                log.info("briefing — injecting rep notes (%d chars)", len(rep_notes))
                print("       injecting rep notes from linked session")

        try:
            briefing_data = generate_briefing(
                transcript_text=transcript_for_briefing,
                transcript_name=transcript_name,
                notes_dir=project_dir,
            )
        except Exception:
            # Briefing failure is non-fatal — the notes have already been updated.
            # Log the error and continue; the run still counts as complete.
            log.exception("briefing FAILED — skipping, pipeline will still complete")
            print("  ✗  briefing failed (see run.log) — continuing")
            briefing_data     = {}
            briefing_json_str = "{}"
            briefing_at       = ""
            _mark_done(run_dir, state, "briefing", result={"error": "briefing failed"})
        else:
            briefing_json_str = json.dumps(briefing_data, indent=2, ensure_ascii=False)
            briefing_at       = briefing_data.get("generated_at", "")

            # Save briefing.json to run folder for inspection / GUI serving.
            (run_dir / "briefing.json").write_text(briefing_json_str, encoding="utf-8")

            # Save briefing.md — human-readable version in the run folder.
            _write_briefing_md(run_dir, briefing_data)

            log.info("briefing — done at %s", briefing_at)
            print(f"       briefing generated at {briefing_at}")
            _mark_done(run_dir, state, "briefing", result=briefing_data)

    # ── Step 6: email HTML ───────────────────────────────────────────────────
    # Skipped for reruns (same guard as step 5).
    # Pure template rendering — no Claude calls.
    # Reads the briefing dict produced in step 5 and renders a styled HTML file.
    if not run_briefing:
        print("  –  email_html (skipped — rerun)")
        log.info("email_html — skipped (run_briefing=False)")
        email_html_str = ""
    elif _is_done(state, "email_html"):
        print("  ↩  email_html (skipping)")
        log.info("email_html — skipping (already done)")
        email_html_str = (run_dir / "email.html").read_text(encoding="utf-8")
    else:
        print("  ▶  email_html (rendering) ...")
        log.info("email_html — starting")
        try:
            briefing_dict  = json.loads(briefing_json_str) if briefing_json_str and briefing_json_str != "{}" else {}
            email_html_str = generate_email_html(briefing_dict)
            (run_dir / "email.html").write_text(email_html_str, encoding="utf-8")
            log.info("email_html — done (%d chars)", len(email_html_str))
            print(f"       email.html written ({len(email_html_str):,} chars)")
            _mark_done(run_dir, state, "email_html", result={"chars": len(email_html_str)})
        except Exception:
            log.exception("email_html FAILED — skipping")
            print("  ✗  email_html failed (see run.log) — continuing")
            email_html_str = ""
            _mark_done(run_dir, state, "email_html", result={"error": "email_html failed"})

    # ── Build final result ───────────────────────────────────────────────────
    # briefing_json_str, briefing_at, and email_html_str are kept separate from
    # the main result so worker.py can store them in their own DB columns.
    result = {
        **apply_result,
        "tokens":        tokens,
        "reasoning":     reasoning,
        "phase1_edits":  len(edits),        # total proposed (valid + invalid)
        "valid_edits":   len(valid_edits),  # passed validation, sent to apply
        "briefing":      briefing_json_str, # full briefing JSON string → briefing column
        "briefing_at":   briefing_at,       # when briefing was generated → briefing_at column
        "email_html":    email_html_str,    # styled HTML email → email_html column
        "run_dir":       str(run_dir),      # absolute path to run folder → run_dir column
    }

    print(f"{'─' * 60}\n")
    return result


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def _write_summary(
    run_dir: Path,
    name: str,
    edits: list,
    tokens: int,
    apply_result: dict,
    reasoning: str = "",
):
    """Write a human-readable markdown summary of the run to run_dir/summary.md."""
    valid_edits   = [e for e in edits if e.get("_valid")]
    invalid_edits = [e for e in edits if not e.get("_valid")]
    applied  = apply_result.get("applied", [])
    failed   = apply_result.get("failed", [])
    skipped  = apply_result.get("skipped", [])
    commit   = apply_result.get("commit_hash") or "none"

    lines = [
        f"# {name}",
        f"Date: {now_pt()}",  # Pacific time — matches what's stored in the DB
        "",
        "## Phase 1: Extract",
        f"- Tokens: {tokens:,}",
        f"- Proposed: {len(edits)}  ·  Valid: {len(valid_edits)}  ·  Invalid: {len(invalid_edits)}",
    ]
    # Always include Claude's reasoning — most valuable when edits=[] to explain why.
    if reasoning:
        lines += ["", f"**Claude's reasoning:** {reasoning}"]
    if invalid_edits:
        lines += ["", "### Invalid (dropped before apply)"]
        for e in invalid_edits:
            lines.append(f"  - `{e.get('file_path')}` — {e.get('_error')} — {e.get('field_label')}")

    lines += [
        "",
        "## Phase 2: Apply",
        f"- Applied: {len(applied)}  ·  Failed: {len(failed)}  ·  Skipped: {len(skipped)}",
        f"- Commit:  {commit}",
    ]
    if applied:
        lines += ["", "### Applied"]
        for a in applied:
            lines.append(f"  - `{a.get('file')}` — {a['edit'].get('field_label')}")
    if failed:
        lines += ["", "### Failed"]
        for f_ in failed:
            edit = f_.get("edit") or {}
            lines.append(f"  - `{edit.get('file_path', '?')}` — {f_.get('error')} — {edit.get('field_label', '')}")
    if skipped:
        lines += ["", "### Skipped (unknown file path)"]
        for s in skipped:
            edit = s.get("edit") or {}
            lines.append(f"  - `{edit.get('file_path')}` — {edit.get('field_label')}")

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_briefing_md(run_dir: Path, briefing: dict):
    """Assemble and write a human-readable briefing.md to the run folder."""
    name         = briefing.get("transcript_name", "")
    generated_at = briefing.get("generated_at", "")

    lines = [
        f"# Post-Call Briefing — {name}",
        f"Generated: {generated_at}",
        "",
        "## Summary",
        briefing.get("summary", ""),
        "",
        "## Attendees",
        briefing.get("attendees", ""),
        "",
        "## Topics Covered",
        briefing.get("topics", ""),
        "",
        "## Key Items",
        briefing.get("key_items", ""),
        "",
        "## Action Items",
        briefing.get("action_items", ""),
        "",
        "## Follow-Up Email Draft",
        briefing.get("email_draft", ""),
        "",
        "---",
        "## Engagement Context (used for this briefing)",
        briefing.get("engagement_context", ""),
    ]
    (run_dir / "briefing.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run transcript pipeline with checkpointing")
    parser.add_argument("transcript_path", help="Path to transcript .txt file")
    parser.add_argument("--name",        default=None,           help="Run name (default: filename stem)")
    parser.add_argument("--project-dir", default=str(NOTES_DIR), help="Notes directory")
    args = parser.parse_args()

    name = args.name or Path(args.transcript_path).stem
    asyncio.run(run_pipeline(args.transcript_path, name, args.project_dir))
