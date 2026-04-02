# Sundial CRM — FastAPI server (Python port of server.js)
# Usage: uvicorn server:app --port 3001 --reload
# Opens at http://localhost:3001
#
# Requires inngest dev server running in parallel:
#   inngest dev -u http://localhost:3001/api/inngest

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from logging_config import setup_logging, get_logger
setup_logging()
log = get_logger("server")

import inngest
import inngest.fast_api
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import apply logic from the Python port
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "apply_edits", Path(__file__).parent / "scripts/phase-2/apply_edits.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
apply_batch = _mod.apply_batch
track_read  = _mod.track_read

# Import Inngest client and functions
from inngest_functions import inngest_client, extract_transcript

app = FastAPI()

# Mount Inngest — registers POST /api/inngest for the dev server to call
inngest.fast_api.serve(app, inngest_client, [extract_transcript])

BASE_DIR            = Path(__file__).parent
PROJECT_DIR         = BASE_DIR / "test-data" / "golden-eagle"
CALLS_LOG           = BASE_DIR / "test-data" / "calls.json"
NAMED_VERSIONS_FILE = BASE_DIR / "test-data" / "named-versions.json"

# ── Request models ───────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    transcript: str
    callName: str | None = None
    callDate: str | None = None

class ApplyRequest(BaseModel):
    callId: str | None = None
    edits: list[dict]

class NewFileRequest(BaseModel):
    name: str
    location: str = "root"

class SaveFileRequest(BaseModel):
    file_path: str
    content: str

class CommitCheckpointRequest(BaseModel):
    file_path: str
    content: str

class ProtectVersionRequest(BaseModel):
    hash: str
    name: str

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_project_files() -> dict[str, str]:
    files = {}
    for full in PROJECT_DIR.rglob("*.md"):
        rel = str(full.relative_to(PROJECT_DIR))
        files[rel] = full.read_text(encoding="utf-8")
    return files

def load_calls_log() -> list:
    if not CALLS_LOG.exists():
        return []
    return json.loads(CALLS_LOG.read_text(encoding="utf-8"))

def save_calls_log(calls: list) -> None:
    CALLS_LOG.write_text(json.dumps(calls, indent=2), encoding="utf-8")

def load_named_versions() -> list:
    if not NAMED_VERSIONS_FILE.exists():
        return []
    return json.loads(NAMED_VERSIONS_FILE.read_text(encoding="utf-8"))

def format_age(date_str: str) -> str:
    try:
        then = datetime.fromisoformat(date_str)
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        diff_ms = (datetime.now(timezone.utc) - then).total_seconds() * 1000
        mins  = int(diff_ms / 60000)
        hours = int(diff_ms / 3600000)
        days  = int(diff_ms / 86400000)
        if mins  <  1: return "just now"
        if mins  < 60: return f"{mins}m ago"
        if hours < 24: return f"{hours}h ago"
        return f"{days}d ago"
    except Exception:
        return ""

def classify_commit(subject: str) -> str:
    if subject.startswith("call:"):        return "ai-post"
    if subject.startswith("snapshot:"):    return "ai-pre"
    if subject.startswith("checkpoint:"): return "checkpoint"
    if subject.startswith("new file:"):   return "new-file"
    if subject.startswith("manual edit:"): return "manual"
    return "other"

def safe_in_project(file_path: str) -> Path:
    """Resolve path and verify it's inside PROJECT_DIR. Raises HTTPException on violation."""
    absolute = (PROJECT_DIR / file_path).resolve()
    if not absolute.is_relative_to(PROJECT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return absolute

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/files")
def get_files():
    try:
        return load_project_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/calls")
def get_calls():
    return load_calls_log()

@app.post("/api/extract")
async def extract(req: ExtractRequest):
    """Non-blocking: queues the transcript for async processing via Inngest."""
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is required")

    call_id = f"call_{int(datetime.now().timestamp() * 1000)}"
    calls   = load_calls_log()
    calls.append({
        "id":          call_id,
        "name":        req.callName or f"Call {len(calls) + 1}",
        "date":        req.callDate or None,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "status":      "queued",
        "edits":       [],
        "transcript":  req.transcript,
        "token_count": None,
    })
    save_calls_log(calls)

    await inngest_client.send(inngest.Event(
        name="sundial/extract.requested",
        data={
            "call_id":    call_id,
            "transcript": req.transcript,
            "call_name":  req.callName or f"Call {len(calls)}",
            "call_date":  req.callDate,
        },
    ))
    log.info("queued extraction — callId=%s name=%s transcript_len=%d",
             call_id, req.callName or "unnamed", len(req.transcript))

    return {"callId": call_id, "status": "queued"}

@app.get("/api/call-status/{call_id}")
def get_call_status(call_id: str):
    """Polling endpoint — frontend checks this every 2s after queueing a call."""
    calls = load_calls_log()
    call  = next((c for c in calls if c["id"] == call_id), None)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return {
        "callId":      call["id"],
        "status":      call["status"],   # queued | pending | failed | applied
        "token_count": call.get("token_count"),
        "edits":       call.get("edits", []),
        "error":       call.get("error"),
    }

@app.post("/api/apply")
async def apply(req: ApplyRequest):
    if not req.edits:
        raise HTTPException(status_code=400, detail="edits array is required")

    call_record = None
    if req.callId:
        call_record = next((c for c in load_calls_log() if c["id"] == req.callId), None)
    call_name = (call_record or {}).get("name", req.callId or "unknown")
    transcript = (call_record or {}).get("transcript", "")

    log.info("apply START — callId=%s name=%s edits=%d transcript_present=%s",
             req.callId, call_name, len(req.edits), bool(transcript))

    # Pre-AI snapshot — commit current state before touching anything
    try:
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "add", "-A"],
            capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "commit", "-m", f"snapshot: before {call_name}"],
            capture_output=True, check=True
        )
        log.info("git snapshot created before apply")
    except subprocess.CalledProcessError as e:
        log.info("git snapshot skipped (nothing to commit): %s", e.stderr.decode().split('\n')[0])

    # Track all files as read before applying
    project_files = load_project_files()
    for rel_path in project_files:
        track_read(str(PROJECT_DIR / rel_path))
    log.info("tracked %d project files for staleness check", len(project_files))

    try:
        result = await apply_batch(req.edits, str(PROJECT_DIR), transcript, call_name)
    except Exception as e:
        log.exception("apply_batch raised an exception — callId=%s", req.callId)
        raise HTTPException(status_code=500, detail=f"apply_batch failed: {e}")

    # Update call status — only 'applied' if at least one edit landed
    if req.callId:
        calls = load_calls_log()
        call = next((c for c in calls if c["id"] == req.callId), None)
        if call:
            if result["applied"]:
                call["status"] = "applied"
                call["applied_at"] = datetime.now(timezone.utc).isoformat()
                call["commit_hash"] = result["commit_hash"]
                call["applied_edits"] = req.edits
                log.info("apply SUCCESS — callId=%s applied=%d commit=%s",
                         req.callId, len(result["applied"]), result["commit_hash"])
            else:
                call["last_apply_attempt"] = datetime.now(timezone.utc).isoformat()
                log.error("apply ZERO_APPLIED — callId=%s failed=%d skipped=%d — ALL EDITS FAILED",
                          req.callId, len(result["failed"]), len(result["skipped"]))
                call["last_apply_failures"] = [
                    {"file": f.get("file") or f.get("edit", {}).get("file_path"), "error": f.get("error")}
                    for f in result["failed"]
                ]
                print(f"[apply] 0 edits applied — failures: {json.dumps(result['failed'], indent=2)}")
            save_calls_log(calls)

    updated_files = load_project_files()

    if result["failed"]:
        print(f"[apply] failed edits: {json.dumps(result['failed'], indent=2)}")
    print(f"[apply] applied={len(result['applied'])} failed={len(result['failed'])} skipped={len(result['skipped'])} commit={result['commit_hash']}")

    return {
        "applied": len(result["applied"]),
        "failed": result["failed"],
        "skipped": result["skipped"],
        "commitHash": result["commit_hash"],
        "files": updated_files,
    }

@app.get("/api/inngest-status")
def inngest_status():
    """Returns whether Inngest appears to be processing jobs.
    If calls have been stuck in 'queued' for >60s, Inngest dev server is likely not running."""
    calls = load_calls_log()
    now = datetime.now(timezone.utc)
    stuck = []
    for c in calls:
        if c.get("status") != "queued":
            continue
        try:
            ts = datetime.fromisoformat(c["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_secs = (now - ts).total_seconds()
            if age_secs > 60:
                stuck.append({"id": c["id"], "name": c["name"], "age_secs": int(age_secs)})
        except Exception:
            pass
    connected = len(stuck) == 0
    if stuck:
        log.warning("inngest-status: %d call(s) stuck in queued — Inngest dev server may not be running: %s",
                    len(stuck), [s["id"] for s in stuck])
    return {"connected": connected, "stuck_count": len(stuck), "stuck_calls": stuck}

@app.post("/api/new-file")
def new_file(req: NewFileRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    rel_path = f"people/{slug}.md" if req.location == "people" else f"{slug}.md"
    absolute_path = (PROJECT_DIR / rel_path).resolve()

    if not absolute_path.is_relative_to(PROJECT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if absolute_path.exists():
        raise HTTPException(status_code=409, detail="File already exists")

    starter = (
        f"# {name}\nGolden Eagle Log Homes\n\n(no notes yet)\n"
        if req.location == "people"
        else f"# {name}\n\n(no notes yet)\n"
    )

    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_text(starter, encoding="utf-8")

    try:
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "add", str(absolute_path)],
            capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "commit", "-m", f"new file: {rel_path}"],
            capture_output=True, check=True
        )
    except subprocess.CalledProcessError:
        pass

    return {"relPath": rel_path, "content": starter}

@app.post("/api/save-file")
def save_file(req: SaveFileRequest):
    absolute_path = safe_in_project(req.file_path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    absolute_path.write_text(req.content, encoding="utf-8")
    return {"ok": True}

@app.post("/api/commit-checkpoint")
def commit_checkpoint(req: CommitCheckpointRequest):
    absolute_path = safe_in_project(req.file_path)
    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    absolute_path.write_text(req.content, encoding="utf-8")

    commit_hash = None
    try:
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "add", str(absolute_path)],
            capture_output=True, check=True
        )
        subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "commit", "-m", f"checkpoint: {req.file_path}"],
            capture_output=True, check=True
        )
        result = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "rev-parse", "--short", "HEAD"],
            capture_output=True, check=True
        )
        commit_hash = result.stdout.decode().strip()
    except subprocess.CalledProcessError:
        pass  # Nothing to commit — file unchanged since last save

    return {"ok": True, "commitHash": commit_hash}

@app.post("/api/retry-queued")
async def retry_queued():
    """Re-sends Inngest extract events for all calls stuck in 'queued' status.
    Use when Inngest dev server was restarted and events were lost."""
    calls = load_calls_log()
    queued = [c for c in calls if c.get("status") == "queued"]
    if not queued:
        return {"retried": 0, "call_ids": []}

    retried = []
    for call in queued:
        await inngest_client.send(inngest.Event(
            name="sundial/extract.requested",
            data={
                "call_id":    call["id"],
                "transcript": call.get("transcript", ""),
                "call_name":  call.get("name", call["id"]),
                "call_date":  call.get("date"),
            },
        ))
        retried.append(call["id"])
        log.info("retry-queued: re-sent event for callId=%s name=%s", call["id"], call.get("name"))

    log.info("retry-queued: re-sent %d events", len(retried))
    return {"retried": len(retried), "call_ids": retried}

@app.post("/api/protect-version")
def protect_version(req: ProtectVersionRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="hash and name are required")

    named = load_named_versions()
    entry = {"hash": req.hash, "name": name, "created": datetime.now(timezone.utc).isoformat()}
    existing = next((i for i, n in enumerate(named) if n["hash"] == req.hash), -1)
    if existing != -1:
        named[existing] = entry
    else:
        named.append(entry)

    NAMED_VERSIONS_FILE.write_text(json.dumps(named, indent=2), encoding="utf-8")
    return {"ok": True}

@app.get("/api/history")
def get_history():
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "log", "--format=%H|%h|%s|%aI", "-50", "--", "."],
            capture_output=True, check=True
        )
        raw = result.stdout.decode().strip()
        if not raw:
            return []

        named = load_named_versions()
        named_by_hash = {n["hash"]: n for n in named}

        entries = []
        for line in raw.split("\n"):
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            hash_, short_hash, subject, date = parts
            commit_type = classify_commit(subject)
            auto_milestone = commit_type in ("ai-post", "ai-pre")
            entries.append({
                "hash": hash_,
                "shortHash": short_hash,
                "subject": subject,
                "date": date,
                "age": format_age(date),
                "type": commit_type,
                "milestone": auto_milestone,
                "named": named_by_hash.get(hash_) or None,
            })

        return entries
    except subprocess.CalledProcessError:
        return []

# ── Static files — mount LAST so API routes aren't shadowed ─────────────────
app.mount("/", StaticFiles(directory=str(BASE_DIR / "app"), html=True), name="static")
