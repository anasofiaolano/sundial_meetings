# Inngest Queue — Implementation Plan

## What changes

**Before:** `POST /api/extract` blocks for 10–30s while Claude runs. One at a time.

**After:** `POST /api/extract` returns in ~50ms with `{callId, status: "queued"}`. Inngest processes asynchronously. Frontend polls until done. Multiple transcripts can be queued simultaneously.

---

## Architecture

```
POST /api/extract
  → create "queued" call record in calls.json
  → send "sundial/extract.requested" event to Inngest
  → return {callId, status: "queued"}         ← responds immediately

Inngest worker (runs in background):
  Step 1: count-tokens    — validates token budget
  Step 2: claude-extract  — calls Claude sonnet
  Step 3: validate-edits  — checks old_values against files
  Step 4: save-call       — writes edits to calls.json, status → "pending"

  On failure after 3 retries:
    → status → "failed", error recorded

Frontend:
  → polls GET /api/call-status/{callId} every 2s
  → queued  → shows spinner
  → pending → shows review screen (same as before)
  → failed  → shows error + "Try again" button
```

---

## Files

| File | Change |
|------|--------|
| `requirements.txt` | add `inngest>=0.4.0` |
| `inngest_functions.py` | **new** — Inngest client + 4-step extract function + failure handler |
| `server.py` | mount Inngest, rewrite `/api/extract`, add `GET /api/call-status/{call_id}` |
| `app/index.html` | polling loop, queued/failed states, stop polling on modal open |
| `ecosystem.config.js` | **new** — pm2 two-process config (uvicorn + inngest dev) |

---

## Steps

- [ ] Step 1 — `requirements.txt` — add inngest
- [ ] Step 2 — `inngest_functions.py` — client + 4-step function
- [ ] Step 3 — `server.py` — mount Inngest, rewrite /api/extract, add /api/call-status
- [ ] Step 4 — `app/index.html` — polling, queued/failed states
- [ ] Step 5 — `ecosystem.config.js` — pm2 two-process setup

---

## Dev setup change

Currently: one terminal, `uvicorn server:app --port 3001 --reload`

With Inngest: **two terminals**:
```bash
# Terminal 1
uvicorn server:app --port 3001 --reload

# Terminal 2
inngest dev -u http://localhost:3001/api/inngest
```

Inngest dev server runs at `http://localhost:8288` — dashboard shows all jobs, retries, DLQ.

Mac Mini: pm2 ecosystem file handles both processes automatically.

---

## Key gotchas

| Issue | Detail |
|---|---|
| Step return values must be JSON-serializable | No Pydantic models or SDK objects across step boundaries — plain dicts only |
| Steps are memoized on retry | Only the failing step re-runs; earlier steps (including the expensive Claude call) are replayed from Inngest's log — no double-billing |
| Token limit error should not retry | `ValueError` for token budget exceeded → mark as non-retryable so Inngest doesn't retry 3 times on a known-bad transcript |
| `inngest dev` must be running | Without it, events queue but nobody processes them |
| `save_calls_log` not thread-safe | Fine with single uvicorn worker; same constraint as `read_file_state` in apply_edits.py |
