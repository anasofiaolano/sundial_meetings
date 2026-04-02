# Sundial CRM — FastAPI server (Python port of server.js)
# Usage: uvicorn server:app --port 3001 --reload
# Opens at http://localhost:3001

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from anthropic import AsyncAnthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import apply logic from the Python port
import importlib.util, sys as _sys
_spec = importlib.util.spec_from_file_location(
    "apply_edits", Path(__file__).parent / "scripts/phase-2/apply_edits.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
apply_batch = _mod.apply_batch
track_read  = _mod.track_read

app = FastAPI()
client = AsyncAnthropic()

BASE_DIR            = Path(__file__).parent
PROJECT_DIR         = BASE_DIR / "test-data" / "golden-eagle"
CALLS_LOG           = BASE_DIR / "test-data" / "calls.json"
NAMED_VERSIONS_FILE = BASE_DIR / "test-data" / "named-versions.json"

# ── Shared extraction config (mirrors scripts/phase-1/run-all.js) ───────────

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
    if not req.transcript.strip():
        raise HTTPException(status_code=400, detail="transcript is required")

    project_files = load_project_files()
    file_context = "\n\n---\n\n".join(
        f"[FILE: {rel}]\n{content}" for rel, content in project_files.items()
    )
    user_message = f"## Call Transcript\n{req.transcript}\n\n---\n\n## Current Project Files\n{file_context}"
    messages = [{"role": "user", "content": user_message}]

    count = await client.messages.count_tokens(
        model="claude-sonnet-4-6", system=SYSTEM_PROMPT, messages=messages
    )

    if count.input_tokens > 160_000:
        raise HTTPException(
            status_code=400,
            detail=f"Token budget exceeded: {count.input_tokens:,}"
        )

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=messages,
        tools=[{"name": "propose_edits", "description": "Output the proposed edits array", "input_schema": TOOL_SCHEMA}],
        tool_choice={"type": "tool", "name": "propose_edits"},
    )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if not tool_use:
        raise HTTPException(status_code=500, detail="No tool_use block in response")

    raw_edits = tool_use.input.get("edits", [])
    known_paths = set(project_files.keys())

    edits = [
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

    call_id = f"call_{int(datetime.now().timestamp() * 1000)}"
    calls = load_calls_log()
    calls.append({
        "id": call_id,
        "name": req.callName or f"Call {len(calls) + 1}",
        "date": req.callDate or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "token_count": count.input_tokens,
        "edits": edits,
        "transcript": req.transcript,
        "status": "pending",
    })
    save_calls_log(calls)

    return {"callId": call_id, "edits": edits, "token_count": count.input_tokens}

@app.post("/api/apply")
async def apply(req: ApplyRequest):
    if not req.edits:
        raise HTTPException(status_code=400, detail="edits array is required")

    call_record = None
    if req.callId:
        call_record = next((c for c in load_calls_log() if c["id"] == req.callId), None)
    call_name = (call_record or {}).get("name", req.callId or "unknown")
    transcript = (call_record or {}).get("transcript", "")

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
    except subprocess.CalledProcessError:
        pass  # Nothing to commit — that's fine

    # Track all files as read before applying
    project_files = load_project_files()
    for rel_path in project_files:
        track_read(str(PROJECT_DIR / rel_path))

    result = await apply_batch(req.edits, str(PROJECT_DIR), transcript, call_name)

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
            else:
                call["last_apply_attempt"] = datetime.now(timezone.utc).isoformat()
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
