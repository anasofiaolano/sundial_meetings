# server.py
#
# Thin HTTP API for submitting transcripts and checking job status.
# The worker (worker.py) does the actual processing — this just writes to jobs.db.
#
# Usage:
#   uvicorn backend.server:app --port 3003 --reload
#
# Endpoints:
#   POST /api/queue           — submit a transcript job (by file path)
#   GET  /api/jobs            — list all jobs (newest first)
#   GET  /api/jobs/{id}       — get one job by ID
#   GET  /api/calls           — jobs + transcript text + briefing from runs/ folder
#   GET  /api/files           — {rel: content} of all project files
#   POST /api/files/{path}    — save a project file
#   POST /api/upload          — upload transcript text and queue it

import hashlib
import json
import logging
import logging.config
import sqlite3
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
import uuid
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

# ── Path setup ───────────────────────────────────────────────────────────────
# Must happen before importing from utils/ — uvicorn imports server.py as a
# module so utils/ is not on sys.path automatically.
BASE_DIR    = Path(__file__).parent   # backend/
ROOT_DIR    = BASE_DIR.parent         # sundial_meetings/
sys.path.insert(0, str(ROOT_DIR / "utils"))
sys.path.insert(0, str(ROOT_DIR / "services"))
sys.path.insert(0, str(ROOT_DIR / "phase-7-chat"))
sys.path.insert(0, str(ROOT_DIR / "copilot"))   # copilot/ package
sys.path.insert(0, str(ROOT_DIR / "pipeline" / "backend"))  # pipeline/ package

from time_utils import now_pt  # noqa: E402 — Pacific-time timestamp (utils/time_utils.py)
from chat import chat_stream   # noqa: E402 — phase-7-chat/chat.py
from routes import copilot_router  # noqa: E402 — copilot/routes.py
from router import pipeline_main_router  # noqa: E402 — pipeline/backend/router.py
import gmail  # noqa: E402 — services/gmail.py

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import google_oauth

NOTES_DIR    = ROOT_DIR / "dummy_data" / "notes"
UPLOADS_DIR  = ROOT_DIR / "dummy_data" / "uploads"  # canonical home for all transcript files
DB_PATH      = BASE_DIR / "jobs.db"
RUNS_DIR     = BASE_DIR / "runs"
FRONTEND_DIR = ROOT_DIR / "frontend"  # source of truth for the GUI

UPLOADS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Structured logging to stdout. uvicorn already captures stdout/stderr so
# these lines appear in the server console and can be piped to a log file.
# exc_info=True on any logger.error() call gives you the full traceback.

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    # Silence noisy third-party loggers
    "loggers": {
        "httpx":          {"level": "WARNING"},
        "httpcore":       {"level": "WARNING"},
        "apscheduler":    {"level": "INFO"},
    },
})

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background email sync (APScheduler)
# ---------------------------------------------------------------------------
# AsyncIOScheduler runs on the same event loop as FastAPI — no extra process,
# no broker. SQLAlchemyJobStore persists job state to SQLite so jobs survive
# server restarts and deploys.
#
# The sync function (gmail.sync_client_emails) is queue-agnostic: it's a plain
# async function that takes a client_id. APScheduler calls it today; migrating
# to a distributed job queue later is a drop-in change to this section only.

def _make_scheduler() -> AsyncIOScheduler:
    jobstore_url = f"sqlite:///{DB_PATH}"
    return AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=jobstore_url)},
        job_defaults={"coalesce": True, "max_instances": 1},
    )


async def _sync_all_clients() -> None:
    """
    Background job: sync Gmail threads for every client that has email filters.
    Runs every 15 minutes via APScheduler. Errors are logged but never crash the job —
    APScheduler will retry on the next interval.
    """
    conn = _connect()
    # Only sync clients that have at least one email filter configured
    client_ids = [
        r["client_id"]
        for r in conn.execute(
            "SELECT DISTINCT client_id FROM client_email_filters"
        ).fetchall()
    ]
    conn.close()

    if not client_ids:
        logger.info("[scheduler] no clients with email filters — skipping sync")
        return

    logger.info("[scheduler] starting email sync for %d client(s)", len(client_ids))
    for client_id in client_ids:
        try:
            await gmail.sync_client_emails(client_id)
        except Exception:
            # Log loudly but keep going — one client failing shouldn't block the rest
            logger.error(
                "[scheduler] sync failed for client=%s", client_id, exc_info=True
            )
    logger.info("[scheduler] email sync complete")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn



def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    # Parse result JSON so the API returns structured data, not a raw string.
    if d.get("result"):
        try:
            d["result"] = json.loads(d["result"])
        except Exception:
            pass
    # Parse briefing JSON so the GUI gets structured sections, not a raw string.
    if d.get("briefing"):
        try:
            d["briefing"] = json.loads(d["briefing"])
        except Exception:
            pass
    return d


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _find_run_dir(job: dict) -> Path | None:
    """Return the run folder for a job, reading directly from the run_dir DB column."""
    if job.get("run_dir"):
        p = Path(job["run_dir"])
        return p if p.exists() else None
    return None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    # Start the background scheduler when the server boots
    scheduler = _make_scheduler()
    scheduler.add_job(
        _sync_all_clients,
        "interval",
        minutes=15,
        id="sync_all_clients",
        replace_existing=True,   # safe to restart without duplicate jobs
    )
    scheduler.start()
    logger.info("[scheduler] started — email sync every 15 minutes")
    yield
    # Graceful shutdown on server stop
    scheduler.shutdown()
    logger.info("[scheduler] stopped")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(copilot_router)
app.include_router(pipeline_main_router)

if not DB_PATH.exists():
    sys.exit(
        f"ERROR: {DB_PATH} not found. Run migrations first:\n"
        f"  python backend/migrate.py"
    )

# Serve the frontend/ directory under /static/.
# Mounting at "/" intercepts /api/* routes even when defined first — mounting
# at "/static" avoids that. index.html is served by the explicit route below.
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.get("/")
def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

class SubmitRequest(BaseModel):
    transcript_path: str
    transcript_name: str
    project_dir:     str = str(NOTES_DIR)
    client_id:       str | None = None


@app.post("/api/queue")
def submit_job(req: SubmitRequest):
    """Insert a pending job by file path. Skips if same content already queued/running/done."""
    p = Path(req.transcript_path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Transcript not found: {req.transcript_path}")

    content      = p.read_text(encoding="utf-8")
    content_hash = _hash(content)

    conn = _connect()
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE content_hash = ? AND status != 'failed' LIMIT 1",
        (content_hash,),
    ).fetchone()
    if existing:
        conn.close()
        return {"id": existing["id"], "status": existing["status"], "skipped": True}

    job_id = str(uuid.uuid4())
    now    = now_pt()
    # Set upload_path if the file already lives in the canonical uploads folder.
    p_resolved       = Path(req.transcript_path).resolve()
    uploads_resolved = UPLOADS_DIR.resolve()
    upload_path = str(p_resolved) if str(p_resolved).startswith(str(uploads_resolved)) else None
    conn.execute(
        """INSERT INTO jobs
           (id, transcript_path, transcript_name, project_dir, status, created_at, content_hash, upload_path, client_id)
           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
        (job_id, req.transcript_path, req.transcript_name, req.project_dir, now, content_hash, upload_path, req.client_id),
    )
    conn.close()
    return {"id": job_id, "status": "pending", "created_at": now}


@app.get("/api/jobs")
def list_jobs():
    conn = _connect()
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    conn = _connect()
    row  = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _row_to_dict(row)


class RenameRequest(BaseModel):
    transcript_name: str


@app.patch("/api/calls/{job_id}")
def rename_call(job_id: str, req: RenameRequest):
    """Rename a call. Run dir lookup uses job_id prefix so the folder name doesn't matter."""
    conn = _connect()
    cur  = conn.execute(
        "UPDATE jobs SET transcript_name = ? WHERE id = ?",
        (req.transcript_name.strip(), job_id),
    )
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


class RerunRequest(BaseModel):
    job_id:      str
    focus_files: list[str] = []


@app.post("/api/rerun")
def rerun_job(req: RerunRequest):
    """Create a new job re-running the same transcript, optionally with a file focus hint."""
    conn = _connect()
    original = conn.execute("SELECT * FROM jobs WHERE id = ?", (req.job_id,)).fetchone()
    if not original:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    focus_hint = None
    if req.focus_files:
        files_list = ", ".join(f"`{f}`" for f in req.focus_files)
        focus_hint = (
            f"This transcript was processed before the following file(s) existed: {files_list}. "
            f"Now that they exist, re-evaluate the transcript with attention to what information "
            f"belongs in each of these files, and whether anything currently in other files "
            f"(e.g. other-notes.md) should be moved there instead."
        )

    job_id = str(uuid.uuid4())
    now    = now_pt()
    conn.execute(
        """INSERT INTO jobs
           (id, transcript_path, transcript_name, project_dir, status, created_at, parent_job_id, focus_hint)
           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
        (job_id, original["transcript_path"], original["transcript_name"],
         original["project_dir"], now, req.job_id, focus_hint),
    )
    conn.close()
    return {"id": job_id, "status": "pending", "created_at": now}


# ---------------------------------------------------------------------------
# Calls — GUI
# ---------------------------------------------------------------------------

@app.get("/api/calls")
@app.get("/api/calls/{client_id}")
def list_calls(client_id: str | None = None):
    """Top-level jobs only (no re-runs), newest-first, with transcript text and briefing if available."""
    conn = _connect()
    if client_id:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE parent_job_id IS NULL AND client_id = ? ORDER BY created_at DESC",
            (client_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE parent_job_id IS NULL ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    calls = []
    for row in rows:
        d       = _row_to_dict(row)
        run_dir = _find_run_dir(d)
        transcript_file = run_dir / "transcript.txt" if run_dir else None
        d["transcript_text"] = (
            transcript_file.read_text(encoding="utf-8")
            if transcript_file and transcript_file.exists()
            else None
        )
        calls.append(d)
    return calls


# ---------------------------------------------------------------------------
# Groups — user-defined client buckets (phase 8)
# ---------------------------------------------------------------------------

class GroupCreateRequest(BaseModel):
    name: str

class GroupUpdateRequest(BaseModel):
    name:     str | None = None
    position: int | None = None


@app.get("/api/groups")
def list_groups():
    conn = _connect()
    rows = conn.execute("SELECT * FROM groups ORDER BY position").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/groups", status_code=201)
def create_group(req: GroupCreateRequest):
    conn = _connect()
    max_pos = conn.execute("SELECT COALESCE(MAX(position), -1) FROM groups").fetchone()[0]
    group_id = f"group-{uuid.uuid4().hex[:8]}"
    now = now_pt()
    conn.execute(
        "INSERT INTO groups (id, name, position, created_at) VALUES (?, ?, ?, ?)",
        (group_id, req.name.strip(), max_pos + 1, now),
    )
    conn.close()
    return {"id": group_id, "name": req.name.strip(), "position": max_pos + 1, "created_at": now}


@app.patch("/api/groups/{group_id}")
def update_group(group_id: str, req: GroupUpdateRequest):
    conn = _connect()
    row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Group not found")
    if req.name is not None:
        conn.execute("UPDATE groups SET name = ? WHERE id = ?", (req.name.strip(), group_id))
    if req.position is not None:
        conn.execute("UPDATE groups SET position = ? WHERE id = ?", (req.position, group_id))
    conn.close()
    return {"ok": True}


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str):
    conn = _connect()
    in_use = conn.execute(
        "SELECT COUNT(*) FROM clients WHERE group_id = ?", (group_id,)
    ).fetchone()[0]
    if in_use:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Group has {in_use} client(s) — reassign them before deleting",
        )
    cur = conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Group not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Clients — one per account/prospect (phase 8)
# ---------------------------------------------------------------------------

class ClientCreateRequest(BaseModel):
    name:           str
    group_id:       str
    next_follow_up: str | None = None  # ISO date YYYY-MM-DD


class ClientUpdateRequest(BaseModel):
    name:           str | None = None
    group_id:       str | None = None
    next_follow_up: str | None = None


def _client_project_dir(client_id: str) -> Path:
    return ROOT_DIR / "dummy_data" / client_id


@app.get("/api/clients")
def list_clients(group_id: str | None = None):
    conn = _connect()
    if group_id:
        rows = conn.execute(
            "SELECT * FROM clients WHERE group_id = ? ORDER BY name", (group_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()

    # Annotate each client with the date of their most recent call
    clients = []
    for row in rows:
        d = dict(row)
        last = conn.execute(
            "SELECT MAX(created_at) FROM jobs WHERE client_id = ? AND parent_job_id IS NULL",
            (d["id"],),
        ).fetchone()[0]
        d["last_call_at"] = last
        clients.append(d)

    conn.close()
    return clients


@app.post("/api/clients", status_code=201)
def create_client(req: ClientCreateRequest):
    conn = _connect()
    if not conn.execute("SELECT 1 FROM groups WHERE id = ?", (req.group_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Group not found")

    client_id   = f"client-{uuid.uuid4().hex[:8]}"
    project_dir = _client_project_dir(client_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    now = now_pt()
    conn.execute(
        """INSERT INTO clients (id, name, group_id, next_follow_up, project_dir, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (client_id, req.name.strip(), req.group_id, req.next_follow_up, str(project_dir), now),
    )
    conn.close()
    return {"id": client_id, "name": req.name.strip(), "group_id": req.group_id,
            "next_follow_up": req.next_follow_up, "project_dir": str(project_dir), "created_at": now}


@app.patch("/api/clients/{client_id}")
def update_client(client_id: str, req: ClientUpdateRequest):
    conn = _connect()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    if req.name is not None:
        conn.execute("UPDATE clients SET name = ? WHERE id = ?", (req.name.strip(), client_id))
    if req.group_id is not None:
        if not conn.execute("SELECT 1 FROM groups WHERE id = ?", (req.group_id,)).fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Group not found")
        conn.execute("UPDATE clients SET group_id = ? WHERE id = ?", (req.group_id, client_id))
    if req.next_follow_up is not None:
        conn.execute("UPDATE clients SET next_follow_up = ? WHERE id = ?", (req.next_follow_up, client_id))
    conn.close()
    return {"ok": True}


@app.delete("/api/clients/{client_id}")
def delete_client(client_id: str):
    conn = _connect()
    cur = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chat — AI assistant (stub; Claude wiring added in phase 7)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    messages:      list  # [{"role": "user"|"assistant", "content": str}]
    context_items: list  # [{"type": "call", "id": "..."} | {"type": "file", "rel": "..."}]


@app.post("/api/chat")
def chat(req: ChatRequest):
    return StreamingResponse(
        chat_stream(req.messages, req.context_items),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Project files — GUI
# ---------------------------------------------------------------------------

@app.get("/api/files/{client_id}")
def list_files(client_id: str):
    """Return {rel_path: content} for all files belonging to a client."""
    conn = _connect()
    rows = conn.execute(
        "SELECT rel_path, content FROM files WHERE client_id = ? ORDER BY rel_path",
        (client_id,),
    ).fetchall()
    conn.close()
    return {r["rel_path"]: r["content"] for r in rows}


class SaveFileRequest(BaseModel):
    content: str


@app.post("/api/files/{client_id}/{path:path}")
def save_file(client_id: str, path: str, req: SaveFileRequest):
    """Upsert a file in the DB and write it to the client's subfolder on disk."""
    conn = _connect()
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    if not client:
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")

    # Sanitise path — prevent directory traversal
    safe_path = Path(path)
    if safe_path.is_absolute() or ".." in safe_path.parts:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid path")

    now = now_pt()
    conn.execute(
        """INSERT INTO files (id, client_id, rel_path, content, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(client_id, rel_path) DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at""",
        (str(uuid.uuid4()), client_id, str(safe_path), req.content, now, now),
    )

    # Mirror to disk inside the client's project_dir
    if client["project_dir"]:
        target = (Path(client["project_dir"]) / safe_path).resolve()
        if str(target).startswith(str(Path(client["project_dir"]).resolve())):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(req.content, encoding="utf-8")

    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chat threads — persistent conversation history
# ---------------------------------------------------------------------------

class ThreadCreateRequest(BaseModel):
    client_id: str
    title:     str = "New conversation"


class MessageSaveRequest(BaseModel):
    messages: list  # [{"role", "content", "context_items"?, "usage"?}]


@app.get("/api/chat/threads/{client_id}")
def list_threads(client_id: str):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM chat_threads WHERE client_id = ? ORDER BY updated_at DESC",
        (client_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/chat/threads", status_code=201)
def create_thread(req: ThreadCreateRequest):
    conn = _connect()
    if not conn.execute("SELECT 1 FROM clients WHERE id = ?", (req.client_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    now = now_pt()
    conn.execute(
        "INSERT INTO chat_threads (id, client_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (thread_id, req.client_id, req.title.strip(), now, now),
    )
    conn.close()
    return {"id": thread_id, "client_id": req.client_id, "title": req.title.strip(),
            "created_at": now, "updated_at": now}


class ThreadUpdateRequest(BaseModel):
    title: str


@app.patch("/api/chat/threads/{thread_id}")
def update_thread(thread_id: str, req: ThreadUpdateRequest):
    conn = _connect()
    row = conn.execute("SELECT 1 FROM chat_threads WHERE id = ?", (thread_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Thread not found")
    now = now_pt()
    conn.execute(
        "UPDATE chat_threads SET title = ?, updated_at = ? WHERE id = ?",
        (req.title.strip(), now, thread_id),
    )
    conn.close()
    return {"ok": True}


@app.delete("/api/chat/threads/{thread_id}")
def delete_thread(thread_id: str):
    conn = _connect()
    cur = conn.execute("DELETE FROM chat_threads WHERE id = ?", (thread_id,))
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"ok": True}


@app.get("/api/chat/threads/{thread_id}/messages")
def get_messages(thread_id: str):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE thread_id = ? ORDER BY created_at",
        (thread_id,),
    ).fetchall()
    conn.close()
    msgs = []
    for r in rows:
        d = dict(r)
        if d.get("context_items"):
            try: d["context_items"] = json.loads(d["context_items"])
            except: pass
        if d.get("usage"):
            try: d["usage"] = json.loads(d["usage"])
            except: pass
        msgs.append(d)
    return msgs


@app.post("/api/chat/threads/{thread_id}/messages", status_code=201)
def save_messages(thread_id: str, req: MessageSaveRequest):
    conn = _connect()
    row = conn.execute("SELECT 1 FROM chat_threads WHERE id = ?", (thread_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Thread not found")
    now = now_pt()
    for msg in req.messages:
        conn.execute(
            """INSERT INTO chat_messages (id, thread_id, role, content, context_items, usage, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                thread_id,
                msg["role"],
                msg["content"],
                json.dumps(msg.get("context_items")) if msg.get("context_items") else None,
                json.dumps(msg.get("usage")) if msg.get("usage") else None,
                now,
            ),
        )
    conn.execute(
        "UPDATE chat_threads SET updated_at = ? WHERE id = ?", (now, thread_id)
    )
    conn.close()
    return {"ok": True, "saved": len(req.messages)}


# ---------------------------------------------------------------------------
# Email OAuth — connect Gmail / Outlook
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OAuth state helpers — DB-backed CSRF tokens
# ---------------------------------------------------------------------------

def _state_create(state: str, provider: str) -> None:
    """Store a new OAuth state token. Sweeps expired tokens (>10 min) on each call."""
    conn = _connect()
    now = now_pt()
    # Sweep states older than 10 minutes
    conn.execute(
        "DELETE FROM oauth_states WHERE created_at < datetime('now', '-10 minutes')"
    )
    conn.execute(
        "INSERT INTO oauth_states (state, provider, created_at) VALUES (?, ?, ?)",
        (state, provider, now),
    )
    conn.close()


def _state_consume(state: str) -> str | None:
    """
    Atomically verify and delete a state token.
    Returns the provider if valid and not expired, None otherwise.
    Deleting on read prevents replay attacks.
    """
    conn = _connect()
    row = conn.execute(
        """SELECT provider FROM oauth_states
           WHERE state = ? AND created_at > datetime('now', '-10 minutes')""",
        (state,),
    ).fetchone()
    if row:
        conn.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    conn.close()
    return row["provider"] if row else None


@app.get("/api/email/connect/google")
def email_connect_google():
    """Redirect the browser to Google's OAuth consent screen."""
    state = google_oauth.generate_state()
    _state_create(state, "google")
    url = google_oauth.build_auth_url(state)
    return RedirectResponse(url)


@app.get("/api/email/callback/google")
async def email_callback_google(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google redirects here after the user approves (or denies) access."""
    frontend_settings = "http://localhost:5174/settings"

    # User denied access
    if error:
        return RedirectResponse(f"{frontend_settings}?email_error={error}")

    # CSRF check — verify and consume the state token atomically
    if not state or not _state_consume(state):
        return RedirectResponse(f"{frontend_settings}?email_error=invalid_state")

    if not code:
        return RedirectResponse(f"{frontend_settings}?email_error=no_code")

    try:
        tokens   = await google_oauth.exchange_code(code)
        userinfo = await google_oauth.get_user_info(tokens["access_token"])
        email    = userinfo.get("email", "")
        expiry   = google_oauth.token_expiry_from_response(tokens)
        now      = now_pt()

        conn = _connect()
        conn.execute(
            """INSERT INTO email_accounts
               (id, provider, email_address, access_token, refresh_token, token_expiry, scopes, status, created_at, updated_at)
               VALUES (?, 'google', ?, ?, ?, ?, ?, 'active', ?, ?)
               ON CONFLICT(provider, email_address) DO UPDATE SET
                 access_token  = excluded.access_token,
                 refresh_token = excluded.refresh_token,
                 token_expiry  = excluded.token_expiry,
                 scopes        = excluded.scopes,
                 status        = 'active',
                 updated_at    = excluded.updated_at""",
            (str(uuid.uuid4()), email,
             tokens["access_token"], tokens.get("refresh_token", ""),
             expiry, tokens.get("scope", ""), now, now),
        )
        conn.close()
        return RedirectResponse(f"{frontend_settings}?email_connected=google")

    except ValueError as e:
        # Scope not granted
        return RedirectResponse(f"{frontend_settings}?email_error=scope_denied")
    except Exception as e:
        return RedirectResponse(f"{frontend_settings}?email_error=exchange_failed")


@app.get("/api/email/accounts")
def list_email_accounts():
    """Return connected accounts — provider + email only, never tokens."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, provider, email_address, status, scopes, created_at, updated_at FROM email_accounts ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/clients/{client_id}/emails")
async def get_client_emails(client_id: str, refresh: bool = False):
    """
    Return email threads for a client.
    ?refresh=true triggers a Gmail sync (incremental or full depending on cursor state)
    before returning. Without it, returns the cached threads immediately.
    The frontend passes refresh=true on page load; the scheduler bypasses this
    endpoint entirely and calls gmail.sync_client_emails() directly.
    """
    if refresh:
        # sync_client_emails handles incremental vs full sync internally,
        # always returns the full cached set after syncing
        return await gmail.sync_client_emails(client_id)
    return gmail.get_cached_threads(client_id)


@app.get("/api/clients/{client_id}/emails/{thread_id}")
def get_email_thread(client_id: str, thread_id: str):
    """Return a single cached email thread with full messages."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM email_threads WHERE client_id = ? AND id = ?",
        (client_id, thread_id),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Thread not found")
    import json as _json
    d = dict(row)
    d["type"]         = "email"
    d["messages"]     = _json.loads(d.get("messages_json") or "[]")
    d["participants"] = _json.loads(d.get("participants") or "[]")
    return d


class EmailFilterRequest(BaseModel):
    type:  str   # 'domain' or 'address'
    value: str


@app.get("/api/clients/{client_id}/email-filters")
def get_client_email_filters(client_id: str):
    """Return all email filters for a client."""
    conn = _connect()
    if not conn.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    rows = conn.execute(
        "SELECT id, type, value, created_at FROM client_email_filters WHERE client_id = ? ORDER BY created_at",
        (client_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/clients/{client_id}/email-filters")
def add_client_email_filter(client_id: str, req: EmailFilterRequest):
    """Add a domain or address filter for a client."""
    if req.type not in ("domain", "address"):
        raise HTTPException(status_code=400, detail="type must be 'domain' or 'address'")
    conn = _connect()
    if not conn.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    value = req.value.strip().lstrip("@") if req.type == "domain" else req.value.strip()
    filter_id = f"cef-{uuid.uuid4()}"
    try:
        conn.execute(
            "INSERT INTO client_email_filters (id, client_id, type, value, created_at) VALUES (?, ?, ?, ?, ?)",
            (filter_id, client_id, req.type, value, now_pt()),
        )
    except Exception:
        conn.close()
        raise HTTPException(status_code=409, detail="Filter already exists")
    conn.close()
    return {"id": filter_id, "type": req.type, "value": value}


@app.delete("/api/clients/{client_id}/email-filters/{filter_id}")
def delete_client_email_filter(client_id: str, filter_id: str):
    """Remove an email filter."""
    conn = _connect()
    conn.execute(
        "DELETE FROM client_email_filters WHERE id = ? AND client_id = ?",
        (filter_id, client_id),
    )
    conn.close()
    return {"ok": True}


@app.delete("/api/email/accounts/{account_id}")
async def delete_email_account(account_id: str):
    """Revoke tokens with Google and remove the account from the DB."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM email_accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Account not found")

    account = dict(row)
    conn.execute("DELETE FROM email_accounts WHERE id = ?", (account_id,))
    conn.close()

    # Revoke with Google so access is removed from the user's account too
    if account["provider"] == "google" and account.get("refresh_token"):
        await google_oauth.revoke_token(account["refresh_token"])

    return {"ok": True}


# ---------------------------------------------------------------------------
# Call sessions — live notetaking during calls
# ---------------------------------------------------------------------------

class SessionCreateRequest(BaseModel):
    client_id: str

class SessionEndRequest(BaseModel):
    job_id: str | None = None  # link to transcript job when ending

class NoteCreateRequest(BaseModel):
    text:        str = ''
    type:        str = 'note'  # note|action|question|commitment|private
    is_bookmark: bool = False
    position:    int = 0

class NoteUpdateRequest(BaseModel):
    text:        str | None = None
    type:        str | None = None
    is_bookmark: bool | None = None


@app.post("/api/sessions", status_code=201)
def create_session(req: SessionCreateRequest):
    conn = _connect()
    if not conn.execute("SELECT 1 FROM clients WHERE id = ?", (req.client_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    session_id = f"session-{uuid.uuid4().hex[:12]}"
    now = now_pt()
    conn.execute(
        """INSERT INTO call_sessions (id, client_id, status, started_at, created_at)
           VALUES (?, ?, 'active', ?, ?)""",
        (session_id, req.client_id, now, now),
    )
    conn.close()
    return {"id": session_id, "client_id": req.client_id, "status": "active",
            "started_at": now, "created_at": now}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    conn = _connect()
    row = conn.execute("SELECT * FROM call_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    session = dict(row)
    notes = conn.execute(
        "SELECT * FROM call_notes WHERE session_id = ? ORDER BY position, created_at",
        (session_id,),
    ).fetchall()
    session["notes"] = [dict(n) for n in notes]
    conn.close()
    return session


@app.get("/api/clients/{client_id}/sessions")
def list_client_sessions(client_id: str):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM call_sessions WHERE client_id = ? ORDER BY created_at DESC",
        (client_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.patch("/api/sessions/{session_id}")
def update_session(session_id: str, req: SessionEndRequest):
    """End a session and optionally link it to a transcript job."""
    conn = _connect()
    row = conn.execute("SELECT * FROM call_sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    now = now_pt()
    conn.execute(
        "UPDATE call_sessions SET status='ended', ended_at=?, job_id=? WHERE id=?",
        (now, req.job_id, session_id),
    )
    conn.close()
    return {"ok": True}


@app.post("/api/sessions/{session_id}/notes", status_code=201)
def add_note(session_id: str, req: NoteCreateRequest):
    conn = _connect()
    if not conn.execute("SELECT 1 FROM call_sessions WHERE id = ?", (session_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    if req.type not in ("note", "action", "question", "commitment", "private"):
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid note type")
    note_id = f"note-{uuid.uuid4().hex[:12]}"
    now = now_pt()
    conn.execute(
        """INSERT INTO call_notes (id, session_id, text, type, is_bookmark, position, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (note_id, session_id, req.text, req.type, int(req.is_bookmark), req.position, now, now),
    )
    conn.close()
    return {"id": note_id, "session_id": session_id, "text": req.text, "type": req.type,
            "is_bookmark": req.is_bookmark, "position": req.position,
            "created_at": now, "updated_at": now}


@app.patch("/api/sessions/{session_id}/notes/{note_id}")
def update_note(session_id: str, note_id: str, req: NoteUpdateRequest):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM call_notes WHERE id = ? AND session_id = ?", (note_id, session_id)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")
    if req.type is not None and req.type not in ("note", "action", "question", "commitment", "private"):
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid note type")
    now = now_pt()
    updates = {"updated_at": now}
    if req.text        is not None: updates["text"]        = req.text
    if req.type        is not None: updates["type"]        = req.type
    if req.is_bookmark is not None: updates["is_bookmark"] = int(req.is_bookmark)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE call_notes SET {set_clause} WHERE id = ?", (*updates.values(), note_id))
    conn.close()
    return {"ok": True}


class SessionLinkRequest(BaseModel):
    job_id: str

@app.post("/api/sessions/{session_id}/link")
def link_session_to_job(session_id: str, req: SessionLinkRequest):
    """Link a session to a transcript job after the fact.
    Notes will appear in the session view but were NOT used by the AI briefing."""
    conn = _connect()
    if not conn.execute("SELECT 1 FROM call_sessions WHERE id = ?", (session_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    conn.execute("UPDATE call_sessions SET job_id = ? WHERE id = ?", (req.job_id, session_id))
    conn.close()
    return {"ok": True}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    conn = _connect()
    conn.execute("DELETE FROM call_notes WHERE session_id = ?", (session_id,))
    cur = conn.execute("DELETE FROM call_sessions WHERE id = ?", (session_id,))
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.delete("/api/sessions/{session_id}/notes/{note_id}")
def delete_note(session_id: str, note_id: str):
    conn = _connect()
    cur = conn.execute(
        "DELETE FROM call_notes WHERE id = ? AND session_id = ?", (note_id, session_id)
    )
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


@app.get("/api/clients/{client_id}/pre-call-brief")
def pre_call_brief(client_id: str):
    """
    Returns the last call's date, name, and a short briefing excerpt plus
    any action items. Used to prime the copilot panel before a call starts.
    """
    conn = _connect()
    row = conn.execute(
        """SELECT id, transcript_name, created_at, briefing
           FROM jobs
           WHERE client_id = ? AND parent_job_id IS NULL AND status = 'done'
           ORDER BY created_at DESC LIMIT 1""",
        (client_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"last_call": None, "action_items": [], "agenda": []}

    briefing = None
    if row["briefing"]:
        try:
            briefing = json.loads(row["briefing"])
        except Exception:
            pass

    action_items = []
    if briefing:
        # Support both list and dict shapes in briefing
        for key in ("action_items", "actions", "next_steps"):
            val = briefing.get(key)
            if isinstance(val, list):
                action_items = [str(i) for i in val[:5]]
                break

    raw_name = row["transcript_name"] or row["id"]
    name = raw_name.replace("/", " ").replace("_", " ").strip()

    return {
        "last_call": {"id": row["id"], "name": name, "date": row["created_at"]},
        "action_items": action_items,
        "agenda": [],  # user-editable agenda items, managed client-side for now
    }


# ---------------------------------------------------------------------------
# Upload — GUI drag-and-drop
# ---------------------------------------------------------------------------

class UploadRequest(BaseModel):
    name:       str
    content:    str
    client_id:  str | None = None
    # Optional override for when the call happened — ISO datetime string.
    # If omitted, defaults to now. Used when uploading a transcript after the fact.
    call_date:  str | None = None
    # Optional session to link — if provided and session belongs to this client,
    # the pipeline will use the rep's notes as context when generating the briefing.
    session_id: str | None = None


@app.post("/api/upload")
def upload_transcript(req: UploadRequest):
    """Save transcript text to disk and queue it. Skips if same content already queued/running/done."""
    content_hash = _hash(req.content)

    conn = _connect()
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE content_hash = ? AND status != 'failed' LIMIT 1",
        (content_hash,),
    ).fetchone()
    if existing:
        conn.close()
        return {"id": existing["id"], "status": existing["status"], "skipped": True}

    safe_name = req.name.replace("/", "_").replace("..", "_").removesuffix(".txt")
    # Save to the canonical uploads folder — dummy_data/uploads/
    path = UPLOADS_DIR / f"{safe_name}.txt"
    path.write_text(req.content, encoding="utf-8")

    job_id     = str(uuid.uuid4())
    created_at = req.call_date or now_pt()  # Use provided date if given, else now
    conn.execute(
        """INSERT INTO jobs
           (id, transcript_path, transcript_name, project_dir, status, created_at, content_hash, upload_path, client_id)
           VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
        (job_id, str(path), safe_name, str(NOTES_DIR), created_at, content_hash, str(path), req.client_id),
    )
    # Link session to this job so the pipeline can use rep notes during briefing generation.
    if req.session_id:
        conn.execute(
            "UPDATE call_sessions SET job_id = ? WHERE id = ? AND client_id = ?",
            (job_id, req.session_id, req.client_id),
        )
    conn.close()
    return {"id": job_id, "status": "pending", "created_at": created_at}
