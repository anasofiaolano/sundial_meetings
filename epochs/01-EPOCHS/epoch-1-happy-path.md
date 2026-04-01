# Epoch 1 — Happy Path + Architecture

**Status:** 📋 Pending Review
**Priority:** 🔴 Critical
**Created:** 2026-03-31
**Last Updated:** 2026-03-31
**Builds on:** none — first epoch

---

## 🚨 Critical Risks — REQUIRED (Read Before Anything Else)

1. **Git as version history backend may silently fail in edge cases.** If the Node process lacks write permissions to the project directory, or the git binary is absent from PATH, all commit operations fail silently unless we explicitly check exit codes and surface errors to the UI. Mitigation: wrap every `git commit` in a try/catch, log to SQLite `events` table, surface a toast notification to the rep. Never assume git succeeded.

2. **Claude's proposed-edits JSON may not match the expected schema.** Claude is an external dependency and may return malformed JSON, partial results, or edits that reference file paths that don't exist. If the API times out mid-stream, we may get a truncated response. Mitigation: validate every response against a strict JSON schema before writing `proposed-edits.json`; on validation failure, write a "extraction failed" state to SQLite and show the rep an error state — never silently drop the call.

3. **Concurrent edit conflict: rep edits a doc field while a proposed edit for that same section is pending.** If both are accepted, we could write conflicting content. Mitigation: when the rep accepts a proposed edit, check if any in-progress direct edits exist for the same file (via SQLite `pending_edits` row); if so, warn the rep before writing. This is a known edge case with a manageable mitigation, not a blocking risk.

4. **Mockup is static HTML with no bundler or build step.** Evolving it into a real app requires adding API fetch() calls, but the existing structure (tabs, panels, proposed-edits module, version history panel) must be preserved exactly. Risk: regressions in UI state during migration. Mitigation: Phase 1 keeps all HTML/CSS unchanged; only adds JS fetch() calls. No structural rewrites until a feature demands it.

---

## What the User Wants — REQUIRED

Sales reps at Golden Eagle log home company spend calls learning critical details — floor plan preferences, people's roles and concerns, project blockers — and then lose those details to bad notes or memory. The CRM solves this: after every call, the system automatically extracts what changed and proposes targeted edits to the project's living documents (floor plan, people profiles, project overview). The rep reviews and accepts in one click. Between calls, they can chat with an AI assistant to make any edit. Every accepted change is versioned, so nothing is ever lost. The result is a project file that stays current automatically, without reps having to manually update anything.

---

## Architecture / Happy Path — REQUIRED

### Components

- **Express/Node backend** — REST API server. Handles file reads/writes, git operations, SQLite queries, and proxies Claude API calls. Runs locally on the rep's machine (or a lightweight server). No database server to manage.
- **Project document files (markdown)** — One file per document type: `floor-plan.md`, `project-overview.md`, `people/lauren-thompson.md`, etc. These are the source of truth for project content. Human-readable, git-tracked.
- **Git repository (per project)** — The project document directory is a git repo. Every accepted edit = one commit. Labels embedded in commit messages: `"Mar 25 call"`, `"Rep edit · Mar 31"`, `"AI chat · Mar 31"`. Version history = `git log`. Diffs = `git diff`.
- **SQLite database** — Structured metadata: calls table (id, date, label, transcript path, status), proposed_edits table (id, call_id, status: pending/accepted/skipped, json payload), tasks table, events table (audit log). Not used for document content — that lives in files.
- **proposed-edits.json** — Temporary file written after AI extraction completes. Consumed by the UI to render the Proposed Edits module. Cleared after all edits are resolved (accepted or skipped).
- **consolidated.txt** — Assembled per call: raw transcript + screenshot descriptions from Claude Vision. Input to the AI extraction step. Written to disk, not kept in memory.
- **Frontend (evolved mockup HTML/JS)** — The existing `mockup/index.html` becomes the real app. No React, no bundler. fetch() calls replace hardcoded data. All existing CSS and UI structure preserved.
- **Claude API (Anthropic)** — Used in two places: (1) post-call AI extraction — reads project files + consolidated.txt, returns proposed edits as JSON; (2) AI assistant chat — reads project files + rep's message, returns proposed edits as JSON.

### Happy Path Flow — Post-Call Extraction

1. Rep uploads MP4 recording or drops transcript file onto call in the UI.
2. Backend extracts frames at key moments (every N seconds or at transcript timestamps) using ffmpeg. Frames saved to `calls/{call-id}/screenshots/`.
3. Claude Vision reads each screenshot frame and returns a one-sentence description. Descriptions appended to `consolidated.txt` alongside the transcript text.
4. Backend sends a single API call to Claude with: system prompt (role + constraints), the full content of all project files for this project, and `consolidated.txt`. Claude returns a JSON array of proposed edits.
5. Backend validates the JSON response against the schema. Writes to `calls/{call-id}/proposed-edits.json`. Inserts row into SQLite `proposed_edits` table with status `pending`.
6. UI polls for (or receives via SSE) the `proposed-edits.json` and renders the Proposed Edits module at the bottom of the call view — file list with inline diffs.
7. Rep clicks "Accept" on a file edit. Frontend calls `POST /api/edits/{id}/accept`. Backend writes the new content to the file, runs `git add <file> && git commit -m "Mar 25 call"`, updates SQLite row to `accepted`.
8. Version history panel for that document now shows the new commit at the top.

### Happy Path Flow — AI Assistant Chat

1. Rep types message in the AI chat panel: *"update the floor plan — Lauren switched to cedar flooring"*.
2. Frontend calls `POST /api/chat` with the message.
3. Backend reads all project files for this project, constructs a prompt (message + file contents), calls Claude API.
4. Claude returns proposed edits JSON (same schema as post-call extraction).
5. Backend writes to `proposed-edits.json` (or appends to open one), inserts SQLite row.
6. UI renders Proposed Edits module (same component, no page jump).
7. Rep accepts. File written, git commit labeled `"AI chat · Mar 31"`.

### Happy Path Flow — Rep Direct Edit

1. Rep clicks on a field value in any document (floor plan, people, overview). Field becomes `contenteditable`.
2. Rep types new value. A 2-second debounce timer starts (resets on each keystroke).
3. On debounce fire: frontend calls `POST /api/files/{file-path}/save` with the new full file content.
4. Backend writes the file to disk. Runs `git add && git commit -m "Rep edit · Mar 31, 2:14pm"`. Updates SQLite events table.
5. No UI confirmation needed — the field value is already showing the new text. A small "saved" indicator fades in/out.

### Happy Path Flow — Version History

1. Rep clicks "Version history" button on any document.
2. Frontend calls `GET /api/files/{file-path}/versions`. Backend runs `git log --oneline -- <file>` and returns list of commits (hash, message, timestamp).
3. UI renders the version history panel (right side, Google Docs-style). Each item shows commit label and date.
4. Rep clicks a version. Frontend calls `GET /api/files/{file-path}/diff?from={hash-1}&to={hash-2}`. Backend runs `git diff <hash-1> <hash-2> -- <file>` and returns structured diff.
5. UI renders inline diff: green highlights for additions, strikethrough for deletions. Banner shows "Showing changes made in [V] vs [V-1]".
6. Rep clicks "Back to current" — panel closes, clean view restored.

---

## Flow Explosion — REQUIRED

### Decision Points

| Point | Branches | What Triggers Each |
|-------|----------|-------------------|
| Transcript available? | Yes: proceed to extraction / No: mark call as "transcript missing", show placeholder | File presence check after upload |
| Claude API response valid? | Valid JSON matching schema: write proposed-edits.json / Invalid or timeout: write error state to SQLite, show UI error | JSON schema validation on response |
| Proposed edit conflicts with concurrent rep edit? | No conflict: write normally / Conflict detected: show warning modal, rep chooses | Check SQLite pending_edits before writing |
| Git commit succeeds? | Success: update SQLite, update UI / Failure: log error, show toast, file is still written | Check git exit code |
| Rep accepts single file vs all | Single: write one file, one commit / All: iterate files, one commit per file (preserves per-file labels) | Button clicked |
| Version history: file has no commits yet? | No history: show "No versions yet" state / Has history: render version list | git log returns empty |
| Rep restores an old version? | Write old content as new commit (append, never overwrite) / Cancel: close panel | Button clicked |

### Input Variants

| Input | Valid | Invalid | Edge Cases |
|-------|-------|---------|------------|
| MP4 upload | Standard MP4 with audio | Corrupted file, wrong format | File over 500MB, no audio track, video-only |
| Transcript text | Well-formed timestamped text | Garbled encoding, empty file | Very short call (under 1 min), language other than English |
| Claude response | JSON array matching schema | Malformed JSON, partial response, rate limit error | Empty array (no edits needed), edits to non-existent files |
| Direct edit content | Valid UTF-8 text | Binary content pasted in | Very long text, markdown with special chars |
| Version hash | Valid 40-char git hash | Truncated hash, hash from different repo | Hash of a deleted file |

### External Dependencies

| Dependency | Happy Path | Fails | Times Out | Returns Unexpected |
|------------|-----------|-------|-----------|-------------------|
| Claude API | Returns valid JSON in <30s | 4xx/5xx: show error state in UI, call marked "extraction failed" in SQLite | After 60s: abort, same as fail | Schema mismatch: validate and reject, don't partially apply |
| git binary | Commit succeeds, returns 0 | Non-zero exit: log to SQLite events, show toast | N/A (local operation) | Unexpected output format: log and alert |
| ffmpeg | Frames extracted cleanly | Not installed: skip screenshot step, proceed with transcript-only extraction | Process hung: kill after 120s | Partial frames: use what was extracted |
| File system | Read/write succeeds | Permission denied: surface error immediately, do not silently fail | N/A | Disk full: catch ENOSPC, show error |
| SQLite | Row writes succeed | DB file corrupt or locked: fall back to file-only operation, log error | N/A | Schema mismatch: migration needed |

### All Flows Discovered

1. **Flow: Standard post-call extraction (full pipeline)**
   - Trigger: Rep uploads MP4 + transcript after a call
   - Steps: Upload → frame extraction → Claude Vision → consolidated.txt → Claude extraction → proposed-edits.json → UI shows module
   - End state: Proposed Edits module visible at bottom of call view

2. **Flow: Transcript-only extraction (no video)**
   - Trigger: Rep uploads transcript file only (no MP4)
   - Steps: Skip ffmpeg step → consolidated.txt = transcript only → Claude extraction → same as above
   - End state: Proposed Edits module visible (fewer context signals, but functional)

3. **Flow: Rep accepts single file edit**
   - Trigger: Rep clicks "Accept" on one file in the Proposed Edits module
   - Steps: POST /api/edits/{id}/accept → backend writes file → git commit → SQLite update → UI marks that file as accepted (collapses, grayed)
   - End state: File updated and versioned; other files remain pending

4. **Flow: Rep accepts all edits**
   - Trigger: Rep clicks "Accept all"
   - Steps: Iterate pending file edits → write each → git commit per file → all SQLite rows updated → module collapses
   - End state: All files updated and versioned

5. **Flow: Rep skips an edit**
   - Trigger: Rep clicks "Skip" on a file edit
   - Steps: SQLite row updated to `skipped` → UI marks file as skipped (fades out)
   - End state: File unchanged, edit recorded as skipped in SQLite (auditable)

6. **Flow: AI assistant chat edit**
   - Trigger: Rep types message in chat panel and sends
   - Steps: POST /api/chat → read project files → Claude API → validate JSON → write proposed-edits.json → SQLite insert → UI shows module
   - End state: Proposed Edits module appears (same component as post-call)

7. **Flow: Rep direct field edit**
   - Trigger: Rep types in a contenteditable field
   - Steps: Keystrokes → 2s debounce → POST /api/files/save → file written → git commit → "saved" indicator
   - End state: File updated, version committed, rep sees confirmation

8. **Flow: Version history browse**
   - Trigger: Rep clicks "Version history" on a document
   - Steps: GET /api/versions → git log → panel opens → rep clicks version → GET /api/diff → git diff → inline diff rendered
   - End state: Rep sees what changed in that version

9. **Flow: Version restore**
   - Trigger: Rep clicks "Restore this version" in history panel
   - Steps: Backend reads content at that commit → writes as current content → git commit labeled "Restored: [version label]" → history panel shows new entry at top
   - End state: Document reflects old content; restore is itself a new version (append-only)

10. **Flow: Extraction failure (Claude error)**
    - Trigger: Claude API returns error or invalid JSON
    - Steps: Catch error → write `{status: "failed", error: "..."}` to SQLite → UI shows error state at bottom of call: "Extraction failed — retry"
    - End state: Call is not lost. Rep can retry extraction. No partial edits written.

11. **Flow: Git commit failure**
    - Trigger: git exits non-zero (permissions, uninitialized repo, merge conflict)
    - Steps: Catch error → file is already written to disk (intentional: prioritize data over version history) → log event to SQLite events table → show toast "File saved but version history failed — [error detail]"
    - End state: Content preserved, version history has a gap. Recoverable by manually running git in the project directory.

12. **Flow: Concurrent edit conflict**
    - Trigger: Rep has an open direct-edit in a field AND a proposed AI edit for the same file is accepted simultaneously
    - Steps: On accept, backend checks SQLite for any `pending_direct_edit` rows on same file path → if found, returns 409 with "Conflict" → UI shows modal: "You have unsaved changes to this file. Accept anyway?" → rep chooses
    - End state: Rep is in control; no silent overwrites.

13. **Flow: New project setup (Golden Eagle onboarding)**
    - Trigger: New project created in the UI
    - Steps: Backend creates directory structure → initializes git repo → creates blank template files (floor-plan.md, project-overview.md, people/) → initial git commit "Project created"
    - End state: Project is live, files exist, version history begins

14. **Flow: Call with no relevant changes**
    - Trigger: Claude extracts from consolidated.txt and determines no project file changes are needed
    - Steps: Claude returns empty array `[]` → UI shows "No proposed edits — no changes detected in this call" at bottom of call view
    - End state: Call is logged, no edits module shown, no confusion

---

## Tool / Pattern Decisions — REQUIRED

### Decision 1: Web Framework

| | Evolve Mockup (Express + vanilla JS) ✅ chosen | Next.js / React |
|---|---|---|
| Setup time to first working API call | ~2 hours (Express + one endpoint) | ~1 day (scaffolding, routing, components) |
| Preserves existing mockup UI | Yes — all HTML/CSS unchanged, just add fetch() | No — must port to JSX, risks regressions |
| Rep can open locally without a build step | Yes — just serve the HTML file | No — requires `npm run build` |
| AI agent can edit without breaking state management | Yes — simple JS functions | Risky — React state, hooks, component tree |
| Debuggability | Open browser console, inspect network tab | Same, but compiled output is harder to trace |
| Long-term scaling if we add a second rep or project | API stays the same; frontend may need componentization | Better for scale, but premature for Phase 1 |
| Who owns the fix path if it breaks | We own it entirely | We own it, but framework version issues add a layer |
| What happens on failure | Direct JS errors in console, easy to diagnose | May surface as obscure React rendering errors |

**Decision:** Evolve the existing mockup with Express + vanilla JS. The mockup already has 100% of the desired UX — rebuilding in React would destroy that work and add complexity with no benefit at this scale.

---

### Decision 2: Version History Mechanism

| | Git commits ✅ chosen | Snapshot JSON array in document file |
|---|---|---|
| Version storage format | One commit per accepted edit; content stored natively in git object store | Append array in each .md file, grows unboundedly |
| Diff computation | `git diff <hash1> <hash2>` — exact, line-level, free | Must implement custom diff algorithm in application code |
| Restore semantics | Write old content as new commit; always append | Same — write old snapshot as new entry |
| Tooling for manual inspection | `git log`, `git show`, `git diff` — any developer can use | Requires custom tooling to read the JSON array |
| Risk: corruption | git object store is battle-tested; corrupt object = one version lost | JSON parse error = entire history unreadable |
| Risk: repo grows large | Text files compress extremely well in git pack files; negligible for project docs | JSON bloat in file; human editors can accidentally break the array |
| Human can edit files directly? | Yes — git tracks the change; may lose attribution label | Yes — but breaks the JSON structure silently |
| Fix path if something goes wrong | `git fsck`, `git reflog` — standard recovery tools | Custom code to repair the JSON array |
| Failure mode | git binary missing or corrupted repo: file still saved, history gap logged | JSON parse error: can't render any version for that doc |

**Decision:** Git commits. The diff tooling is free, the storage format is battle-tested, and the failure mode (history gap) is recoverable. JSON array failure mode (history unreadable) is worse.

---

### Decision 3: Storage Model

| | Files + git only | Files + git + SQLite ✅ chosen | Database only (Postgres/Mongo) |
|---|---|---|---|
| Project document content | In files | In files | In DB records |
| Call metadata (date, label, status) | No structured storage — lose this | SQLite table | DB table |
| Proposed edits state (pending/accepted/skipped) | No way to track | SQLite table | DB table |
| Tasks | No way to track | SQLite table | DB table |
| Query: "show me all pending proposed edits" | Can't — would have to scan JSON files | Single SQL query | Single SQL query |
| Query: "which calls have no transcript yet?" | Can't | Single SQL query | Single SQL query |
| Setup complexity | Zero | Low (SQLite ships with Node via better-sqlite3) | High (DB server, connection string, migrations) |
| Dependency to install | None | better-sqlite3 npm package | pg / mongoose + a running DB server |
| Failure mode: DB unavailable | N/A | App falls back to file-only reads; writes queue to retry | App is completely down |
| Who owns the fix path | N/A | We do; SQLite is a local file | We do, but requires DB server ops |
| Right tool for scale | Fine for 1 rep, 1 project | Fine for 5–10 reps, 50 projects | Needed at 100+ concurrent users |

**Decision:** Files + git + SQLite. Files and git handle document content and version history (where they excel). SQLite handles structured metadata (calls, tasks, edit states) without requiring a server. No over-engineering for current scale.

---

### Decision 4: AI Extraction Output Format

| | Structured JSON schema ✅ chosen | Free-form with parsing |
|---|---|---|
| Schema definition | Array of `{file_path, field_label, old_value, new_value}` objects | Claude returns narrative or markdown; we parse |
| Reliability | Consistent structure; schema validation catches errors immediately | Parsing logic is fragile; edge cases produce silent wrong edits |
| Prompt engineering | System prompt specifies the exact JSON schema | System prompt gives examples; harder to enforce |
| What happens when Claude deviates | JSON parse or schema validation fails; clear error | Parser produces wrong edits; may corrupt files |
| Diff rendering | Exact old_value/new_value available for diff display | Must re-derive the diff from parsed output |
| Who owns the fix path | We fix the schema or the prompt | We fix the parser and the prompt |
| Extensibility | Add fields to schema; update validation | Update parser (and test every edge case again) |

**Decision:** Structured JSON schema. The schema is the contract between Claude and our backend. When Claude deviates, we catch it cleanly at the validation step rather than propagating wrong data.

**Schema (v1):**
```json
[
  {
    "file_path": "floor-plan.md",
    "field_label": "Flooring material",
    "old_value": "undecided",
    "new_value": "cedar",
    "confidence": "high",
    "source_quote": "Lauren said she's now leaning toward cedar for the main floor"
  }
]
```

---

## Phasing

### Phase 1 — MVP: Real data, real files, real git (no AI)

**Goal:** Dogfood the full UI with real Golden Eagle data. Rep can browse real project docs, accept/reject manually seeded proposed edits, and browse real version history. No AI involved.

**What we build:**
- Express server serving project files from disk
- SQLite schema: calls, proposed_edits, tasks, events
- `GET /api/projects/{id}/files/{path}` — reads markdown file, returns content
- `POST /api/edits/{id}/accept` — writes file, runs git commit, updates SQLite
- `POST /api/edits/{id}/skip` — updates SQLite only
- `GET /api/files/{path}/versions` — runs git log, returns version list
- `GET /api/files/{path}/diff` — runs git diff, returns structured diff
- `POST /api/files/{path}/save` — writes file (debounced direct edits), git commit
- Frontend fetch() calls replacing hardcoded data in mockup HTML
- Seed Golden Eagle project: real floor plan, real people, one manually written proposed-edits.json

**What we explicitly defer:** ffmpeg, Claude API, AI chat, call upload pipeline.

**Exit criteria:** Rep (Ana) can open the app, browse real Golden Eagle data, accept a proposed edit and see the file change + version history update, and edit a field directly with the change persisting on reload.

---

### Phase 2 — Post-Call AI Extraction

**Goal:** Upload a real call recording → Claude proposes edits → rep accepts.

**What we build:**
- ffmpeg frame extraction pipeline
- Claude Vision per-frame descriptions → consolidated.txt assembly
- Claude extraction API call with project file context
- JSON schema validation on response
- `POST /api/calls/{id}/process` endpoint
- Error handling: failed extraction state, retry button
- UI: call processing status indicator ("Processing… / Extraction ready / Failed")

**Exit criteria:** Upload one real Golden Eagle call recording → proposed edits appear correctly in the UI → rep accepts → files updated → version history shows the commit.

---

### Phase 3 — AI Assistant Chat + Full Pipeline

**Goal:** Rep can type any instruction in the chat panel → AI proposes edits.

**What we build:**
- `POST /api/chat` endpoint — reads project files + message → calls Claude → validates → returns proposed edits
- Chat history display in the AI panel
- Multi-call context: ability to include recent call summaries in chat context
- Screenshot pipeline refinements (quality, selective extraction)
- Call upload drag-and-drop UX polish

**Exit criteria:** Rep uses the full system for one month of real Golden Eagle calls with no manual backend intervention.

---

## Failure Modes — REQUIRED

| Failure Mode | Likelihood | Mitigation |
|---|---|---|
| Claude API returns malformed JSON | Medium — happens with complex prompts | Schema validation on every response; reject and show error state |
| Claude API rate limit hit | Low (single-user MVP) | Retry with 2s backoff × 3; then surface error; accepted risk at this scale |
| Claude API timeout (>60s) | Low-Medium | Abort after 60s; mark extraction as failed; rep can retry |
| git binary not in PATH | Low (dev machines usually have git) | Check on server startup; show hard error if missing |
| git commit fails (permissions) | Low | Catch exit code; log to SQLite events; show toast; file already written |
| git repo not initialized for project | Low (auto-init on project create) | Check for .git dir before any commit; init if missing |
| SQLite DB file locked (concurrent writes) | Low (single-user) | Use WAL mode; serialize writes via async queue |
| SQLite DB file corrupted | Very Low | Accepted risk: SQLite corruption is rare; DB stores metadata only (docs in files/git) |
| Disk full during file write | Very Low | Catch ENOSPC; surface error immediately; no silent partial write |
| ffmpeg not installed | Medium (new machine setup) | Check on startup; skip frame extraction if missing; proceed transcript-only |
| ffmpeg hangs on malformed MP4 | Low | Kill process after 120s timeout |
| Concurrent rep edit + AI edit conflict | Medium (plausible in real use) | 409 conflict check before accepting; rep prompted to confirm |
| Rep accidentally deletes content in direct edit | Medium (easy to do) | Every direct edit is git committed; rep can restore via version history |
| proposed-edits.json is stale (from a previous call, not yet cleared) | Low | Include call_id in proposed-edits.json; UI validates match before rendering |
| Network error during Claude API call | Low-Medium | Retry × 3; show error state; never leave UI in loading state permanently |
| Rep navigates away mid-extraction | Medium | Extraction runs on backend; rep can return to call view and see status |
| Large project files slow down Claude context | Low (5–10 small markdown files) | Accepted risk at current scale; revisit if files exceed ~10k tokens each |
| Version history panel shows wrong diffs | Low | Always compute diffs fresh from git; never cache diff output |

---

## Engineering Principles Review — REQUIRED

### State & Data Integrity

- [x] **Every state has an exit path.** Proposed edit states: `pending → accepted`, `pending → skipped`, `pending → failed_to_apply`. Call processing states: `uploaded → processing → extraction_ready`, `uploaded → processing → extraction_failed`. Every state has a defined transition. No limbo states — a call can never be stuck in "processing" indefinitely because we set a timeout and write to extraction_failed.
- [x] **Impossible state combinations.** SQLite constraint: a proposed edit cannot be both `accepted` and `skipped`. A call cannot have `extraction_ready` status without a `proposed-edits.json` file existing. We enforce the file existence check before setting that status.
- [x] **Core logic in durable layer.** Document content lives in files (durable) + git (durable). Proposed edit state lives in SQLite (durable). The application layer is thin wiring. Nothing critical lives only in memory.

### Ownership & Dependencies

- [x] **We own every trigger.** No third-party webhooks in the critical path. The rep's action (uploading a file, clicking Accept, typing in a field) directly triggers our own backend endpoint. No black boxes in the write path.
- [x] **Not reimplementing platform features.** Using git for version history (instead of implementing our own diff engine). Using SQLite via better-sqlite3 (not reimplementing persistence). Using ffmpeg for video processing (not reimplementing frame extraction).
- [x] **External dependencies documented.** Claude API, git binary, ffmpeg, file system — all listed in the External Dependencies table with failure handlers.

### Failure & Recovery

- [x] **Retry logic.** Claude API calls: retry × 3 with backoff. File writes: no retry needed (synchronous, fast). Git commits: no retry (failure is logged, file already written — operator can fix git manually).
- [x] **No dead letter queue needed.** This is a single-user system with no async job queue. Failures surface immediately to the rep in the UI. No background jobs that can silently fail.
- [x] **Audit trail is downstream.** SQLite events table is written AFTER the git commit succeeds. Not used as a trigger. Git commit is the source of truth for version history; SQLite is the receipt.

### Observability

- [x] **Alert paths.** This is a single-user local tool — "alerts" manifest as UI error states (toasts, error banners) visible to the rep immediately. Not a multi-tenant SaaS requiring external alerting.
- [x] **Sanity check.** Possible to query SQLite: `SELECT * FROM calls WHERE status = 'processing' AND created_at < datetime('now', '-1 hour')` to find stuck calls. Can be run manually or added as a startup check.
- [x] **Monitoring work flow.** Not applicable at current scale (single user, no background workers). If we add background processing in Phase 3, we add throughput monitoring then.
- [ ] **Catch-all monitors.** Not implemented in Phase 1. Accepted risk — single user, failures surface directly. Add in Phase 3 if background jobs are added.

### Execution Model

- [x] **Right execution model.** No daemons. The Express server handles requests synchronously (or with async/await for I/O). ffmpeg runs as a child process that exits when done. No "while True" loops. No scheduling needed — extraction is triggered by rep action.

### Agent Safety

- [x] **Core logic in durable layers.** Document content: files + git. Proposed edit state: SQLite. An AI agent editing the Express server code cannot corrupt project documents or version history.
- [x] **Architecture doc.** This epoch document serves as the architecture reference. CLAUDE.md will be added to the project root with a pointer to this file and the key constraints (file-first, git for versions, SQLite for metadata).
- [x] **No duplicate building.** Git is the versioning system — we are not implementing a second versioning layer alongside it.

---

## Blind Spot Review — REQUIRED

**Review method:** Solo — fresh-perspective prompt

**Prompt used:**

> You are a different engineer seeing this architecture for the first time. Here is everything we've planned: a CRM for a single sales rep at a log home company. File-first architecture: project documents are markdown files in a git repo. SQLite stores calls, tasks, and proposed edit states. Express/Node backend. The existing mockup HTML becomes the real frontend with fetch() calls added. After each call, Claude reads project files + a consolidated transcript and proposes file edits as JSON. Rep accepts → file written → git commit. Direct edits debounce → git commit. Version history from git log + git diff. AI chat also produces proposed edits via same mechanism. What's missing? What would break? What haven't we considered?

### Findings

**1. The git repo lives WHERE?** The plan says "project document directory is a git repo" but doesn't specify the path or how multiple projects are organized. If the server process changes its working directory, git operations will point at the wrong repo. Fix: the Express server should always resolve absolute paths. The git repo root must be stored in SQLite as part of the project record, not inferred from the working directory.

**2. What happens to proposed-edits.json when the server restarts?** If the server restarts while proposed edits are pending (status = "pending" in SQLite), the UI must be able to re-render the module from SQLite + the JSON file. The current plan re-renders from the file on page load, but if the file is missing (cleaned up early), the pending SQLite rows become orphaned — the UI would show "no pending edits" even though there are unresolved ones. Fix: never delete proposed-edits.json until all rows for that call are resolved.

**3. The debounce saves the full file content, but what IS the full file content?** When a rep edits one field in the floor plan, the frontend sends the full updated file content. But this requires the frontend to be holding the entire current file in memory. If the rep opens a doc, Claude proposes edits to the same doc while the rep has it open, and then the rep saves their edit — their save will overwrite Claude's accepted edits because the frontend's in-memory copy is stale. Fix: on every direct save, the backend must merge the incoming content with the current file-on-disk, or the frontend must always re-fetch before saving.

**4. File path in proposed edits must be validated server-side.** Claude returns `file_path` in the proposed edits JSON. If Claude hallucinates a file path like `../../server.js`, a naive backend would write to that path. Fix: validate that every `file_path` in the proposed edits JSON is within the project directory before writing.

**5. The version history diff UX shows "what changed in this version" — but there's an ambiguity.** When you click a version labeled "Mar 25 call," do you see what changed FROM the previous version TO this version, or the state of the document at that version? The mockup shows the former (diffs vs prior version), but the backend needs to correctly implement `git diff <parent-hash> <this-hash>` rather than `git diff <hash> HEAD`. Make sure the API returns the correct hash pair.

**6. Git commit message collision.** If a rep accepts multiple edits from the same call on different days (e.g., they review the proposed edits days later), the commit message "Mar 25 call" will appear at the wrong date in the git log. The commit message label should come from the call record in SQLite (call.label), not be generated at accept-time from the current date.

**7. No authentication.** This is a local single-user tool in Phase 1, so no auth is needed. But the plan should document this explicitly as an accepted risk, so it isn't accidentally deployed to a shared server without adding auth first.

**8. What does "evolve the mockup" mean operationally?** The mockup is a single HTML file with everything embedded. As we add fetch() calls, the JS will grow. We should establish a convention early: one `<script>` section per major feature (calls, files, edits, chat), rather than one monolithic script block, to keep the file navigable without introducing a bundler.

---

## Convergence Check — OPTIONAL for Epoch 1

| Criterion | Status | Notes |
|-----------|--------|-------|
| All flows have documented handling | ✅ | 14 flows documented including all error branches |
| No unresolved failure modes | ✅ | All failure modes have mitigations or explicit "accepted risk" |
| Delta from previous epoch | N/A | First epoch |
| Staff engineer checklist passes | ✅ | See review above; one deferred item (catch-all monitors) is documented as accepted risk |
| Human sign-off | ⬜ Pending | |

**Staff engineer checklist:**
- [x] No circular dependencies — frontend calls backend; backend calls Claude; no loops
- [x] No unbounded loops or recursion — debounce is bounded; git operations are one-shot
- [x] Every external dependency has a failure handler — Claude, git, ffmpeg, file system all covered
- [x] No single point of failure without recovery — files written before git commit; git failure is logged but not blocking
- [x] Simplest solution that works — vanilla JS + Express + SQLite + git; no unnecessary abstraction
- [x] A senior engineer would approve in design review — file-first with git versioning is a well-understood pattern

**Verdict:** Architecture is converged for Phase 1 scope. Ready for human review. Phase 2 and 3 will each get their own scope document before implementation.

---

## Next Steps

- [x] Happy path documented (5 complete flows)
- [x] Flow explosion complete (14 flows)
- [x] Tool decisions with tradeoff tables (4 decisions)
- [x] Failure modes identified with mitigations (17 failure modes)
- [x] Engineering principles review complete
- [x] Blind spot review complete (8 findings, all addressed)
- [x] HTML deck produced from template
- [ ] ⏸ CHECKPOINT: Human reviews deck (epoch-1-deck.html)
