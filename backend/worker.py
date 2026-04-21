# worker.py
#
# Polls a SQLite jobs table and runs the pipeline for each pending job.
#
# Usage:
#   python worker.py [--db <path>] [--interval <seconds>] [--project-dir <dir>]
#
# The jobs table is created automatically on first run.
# Submit jobs by inserting rows directly or via the server (backend/server.py).

import asyncio
import json
import signal
import sqlite3
import sys
import traceback
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent   # backend/
ROOT_DIR  = BASE_DIR.parent         # sundial_meetings/
NOTES_DIR = ROOT_DIR / "dummy_data" / "notes"

# Add backend and utils to the import path so pipeline and time_utils are found.
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(ROOT_DIR / "utils"))

from pipeline import run_pipeline  # noqa: E402
from time_utils import now_pt      # noqa: E402 — Pacific-time ISO timestamp (utils/time_utils.py)

DEFAULT_DB       = BASE_DIR / "jobs.db"
DEFAULT_INTERVAL = 2.0  # seconds between polls


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _connect(db_path: Path) -> sqlite3.Connection:
    # isolation_level=None enables autocommit — each execute() commits immediately,
    # which is safe for a single-writer worker process.
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row  # rows accessible by column name, not just index
    conn.execute("PRAGMA journal_mode=WAL")  # WAL allows reads while a write is in progress
    return conn


def _ensure_table(conn: sqlite3.Connection):
    """Create the jobs table if it doesn't exist yet (first-run bootstrap)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id               TEXT PRIMARY KEY,
            transcript_path  TEXT NOT NULL,
            transcript_name  TEXT NOT NULL,
            project_dir      TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'pending',
            created_at       TEXT NOT NULL,  -- Pacific time ISO string
            started_at       TEXT,           -- set when worker claims the job
            completed_at     TEXT,           -- set when job finishes (done or failed)
            result           TEXT,           -- JSON result from pipeline (extract/apply stats)
            error            TEXT,           -- traceback if status='failed'
            content_hash     TEXT,           -- SHA-256 of transcript text, for deduplication
            briefing         TEXT,           -- JSON blob: all briefing sections (step 5)
            briefing_at      TEXT            -- Pacific-time ISO when briefing was generated
        )
    """)


def _claim_job(conn: sqlite3.Connection) -> sqlite3.Row | None:
    """
    Atomically claim one pending job: set status='running' and record started_at.
    Returns the row so the worker can read its fields, or None if nothing is pending.
    Oldest job (by created_at) is picked first — FIFO order.
    """
    row = conn.execute(
        "SELECT * FROM jobs WHERE status = 'pending' ORDER BY created_at LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    # Record when the worker picked this job up.
    now = now_pt()
    conn.execute(
        "UPDATE jobs SET status='running', started_at=? WHERE id=?",
        (now, row["id"]),
    )
    return row


def _mark_complete(conn: sqlite3.Connection, job_id: str, result: dict):
    """
    Mark a job done and store the pipeline result.

    briefing and briefing_at are extracted from the result dict and stored in
    their own columns (briefing = JSON string, briefing_at = Pacific ISO string).
    The remaining result dict (extract/apply stats) goes in the result column.
    """
    now = now_pt()

    # Pop dedicated columns out of result so they don't bloat the JSON blob.
    briefing    = result.pop("briefing",    None)
    briefing_at = result.pop("briefing_at", None)
    email_html  = result.pop("email_html",  None)
    run_dir     = result.pop("run_dir",     None)

    conn.execute(
        "UPDATE jobs SET status='done', completed_at=?, result=?, briefing=?, briefing_at=?, email_html=?, run_dir=? WHERE id=?",
        (now, json.dumps(result, ensure_ascii=False), briefing, briefing_at, email_html, run_dir, job_id),
    )


def _mark_failed(conn: sqlite3.Connection, job_id: str, error: str):
    """Mark a job failed and store the traceback string."""
    now = now_pt()
    conn.execute(
        "UPDATE jobs SET status='failed', completed_at=?, error=? WHERE id=?",
        (now, error, job_id),
    )


# ---------------------------------------------------------------------------
# Worker loop
# ---------------------------------------------------------------------------

async def run_worker(
    db_path: Path = DEFAULT_DB,
    poll_interval: float = DEFAULT_INTERVAL,
    project_dir: str = str(NOTES_DIR),
):
    """
    Poll for pending jobs and run them one at a time.
    Runs until cancelled (Ctrl-C or SIGTERM).
    """
    try:
        conn = _connect(db_path)
        _ensure_table(conn)
    except Exception as e:
        print(f"[worker] fatal: could not open DB at {db_path}: {e}")
        return

    # Reset any jobs left in 'running' from a previous process that died.
    # Safe because pipeline.py checkpoints each step — resuming skips completed steps.
    try:
        cur = conn.execute(
            "UPDATE jobs SET status='pending', started_at=NULL WHERE status='running'"
        )
        if cur.rowcount:
            print(f"[worker] reset {cur.rowcount} stuck job(s) from previous run → pending")
    except Exception as e:
        print(f"[worker] warning: could not reset stuck jobs: {e}")

    print(f"Worker started — polling {db_path} every {poll_interval}s")
    print("Press Ctrl-C to stop.\n")

    stop = asyncio.Event()

    def _handle_signal():
        print("\nShutting down worker...")
        stop.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal)
    except Exception as e:
        print(f"[worker] warning: could not register signal handlers: {e}")

    while not stop.is_set():
        # ── claim a job ──────────────────────────────────────────────────────
        try:
            job = _claim_job(conn)
        except Exception as e:
            print(f"[worker] DB error while claiming job: {e}")
            await asyncio.sleep(poll_interval)
            continue

        if job is None:
            await asyncio.sleep(poll_interval)
            continue

        # ── unpack job fields ─────────────────────────────────────────────────
        try:
            job_id       = job["id"]
            name         = job["transcript_name"]
            path         = job["transcript_path"]
            proj_dir     = job["project_dir"] or project_dir
            focus_hint   = job["focus_hint"] if "focus_hint" in job.keys() else None
            # Existing run_dir from DB — passed to pipeline so it can resume
            # from the correct checkpoint folder without filesystem scanning.
            existing_run_dir = job["run_dir"] if "run_dir" in job.keys() else None
            # Reruns (parent_job_id IS NOT NULL) skip the briefing step —
            # they're extract+apply only. Only original parent jobs get briefings.
            run_briefing = job["parent_job_id"] is None
        except Exception as e:
            print(f"[worker] could not read job fields: {e}")
            await asyncio.sleep(poll_interval)
            continue

        print(f"[worker] picked up job {job_id[:8]}  {name}")

        # ── run pipeline ──────────────────────────────────────────────────────
        try:
            result = await run_pipeline(path, name, proj_dir, job_id=job_id, focus_hint=focus_hint, run_briefing=run_briefing, run_dir=existing_run_dir)
        except Exception:
            err = traceback.format_exc()
            print(f"[worker] FAILED  {job_id[:8]}  {name}\n{err}")
            try:
                _mark_failed(conn, job_id, err)
            except Exception as e:
                print(f"[worker] could not mark job {job_id[:8]} failed: {e}")
            continue

        # ── mark complete ─────────────────────────────────────────────────────
        try:
            _mark_complete(conn, job_id, result)
        except Exception as e:
            print(f"[worker] pipeline succeeded but could not update DB for {job_id[:8]}: {e}")
            continue

        n_applied = len(result.get("applied", []))
        n_failed  = len(result.get("failed", []))
        print(f"[worker] done  {job_id[:8]}  {name}  — {n_applied} applied, {n_failed} failed")

    try:
        conn.close()
    except Exception:
        pass
    print("Worker stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase-5 worker: polls jobs.db and runs pipeline")
    parser.add_argument("--db",          default=str(DEFAULT_DB),   help="Path to SQLite jobs DB")
    parser.add_argument("--interval",    default=DEFAULT_INTERVAL,  type=float, help="Poll interval in seconds")
    parser.add_argument("--project-dir", default=str(NOTES_DIR),    help="Notes directory")
    args = parser.parse_args()

    asyncio.run(run_worker(
        db_path=Path(args.db),
        poll_interval=args.interval,
        project_dir=args.project_dir,
    ))
