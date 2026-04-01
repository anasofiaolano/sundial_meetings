# Decision Log

<!--
  INSTRUCTIONS FOR THE AGENT:

  This is your cold context — the decision trail.
  Append-only. NEVER overwrite or delete entries.

  WHEN TO READ:
  - Step 2 of the recovery protocol: read last 20 entries after reading STATE.md
  - When you need to understand WHY a decision was made
  - When STATE.md alone isn't enough context

  WHEN TO WRITE:
  - After every meaningful action (simple entry)
  - After every architectural or tool decision (full decision entry with tradeoff table)
  - The "Why" field is MANDATORY — this is what v1 was missing

  TWO ENTRY TYPES:

  1. SIMPLE ACTION (most entries):
     ### [ISO timestamp] — [title]
     - **Did:** [what was done]
     - **Why:** [why this action was taken]
     - **Files:** [files created/modified]
     - **Impacts:** [other workstreams or components affected, or "none"]

  2. ARCHITECTURE DECISION (when real tradeoffs are evaluated):
     ### [ISO timestamp] — [title]

     | | Option A | Option B (chosen) |
     |---|---|---|
     | [criterion 1] | [value] | [value] |
     | [criterion 2] | [value] | [value] |
     | [criterion 3] | [value] | [value] |

     **Decision:** [choice]. [one sentence why].
     **Files:** [files affected]
     **Impacts:** [workstreams or components affected]
     **Commit:** [git commit hash, if applicable]

  GUIDELINES:
  - Simple entries for routine actions — keep them brief
  - Full decision tables ONLY for architecture choices with real tradeoffs
  - Comparison table columns should be SPECIFIC to the decision (not generic)
  - Include "who owns the fix path" and "what happens on failure" when relevant
  - Reference commit hashes for architecture decisions when using git
-->

*Append-only. Never overwrite. Never delete entries.*
*Read last 20 entries during recovery (Step 2 of protocol).*

---

### 2026-03-31T00:00 — Epoch 1 started: Sundial Meetings CRM

- **Did:** Began Epoch 1. Read all source context: mockup/index.html, docs/ai_file_editing.md, docs/versioning.md. Architecture defined as file-first (project documents as markdown files) + git (version history) + SQLite (structured metadata) + Express/Node backend + evolved mockup frontend.
- **Why:** First epoch for a new project. Architecture-first, no code yet.
- **Files:** `epochs/01-EPOCHS/epoch-1-happy-path.md`, `epochs/01-EPOCHS/epoch-1-deck.html`
- **Impacts:** Establishes all subsequent build decisions

---

### 2026-03-31T00:01 — Decision: Web Framework — Evolve mockup vs. Next.js/React

| | Evolve Mockup (Express + vanilla JS) | Next.js / React |
|---|---|---|
| Preserves existing mockup UI | Yes — all HTML/CSS unchanged, add fetch() only | No — must port to JSX, risks regressions |
| Setup time to first working API | ~2 hours | ~1 day |
| Build step required | No | Yes (npm run build) |
| AI agent can edit safely | Yes — simple JS functions | Risky — React state, component tree |
| Who owns fix path | We own entirely | We own + framework version layer |
| Failure mode | Direct JS errors in console, easy to diagnose | May surface as obscure React rendering errors |
| Long-term scale | Needs componentization later — premature now | Better for scale, but premature for Phase 1 |

**Decision:** Evolve the existing mockup with Express + vanilla JS. The mockup already has 100% of the desired UX built — rebuilding in React destroys that work with no benefit at current scale.
**Files:** `mockup/index.html` (evolved), Express server (to be created in Phase 1)
**Impacts:** All frontend development must preserve existing HTML/CSS structure
**Commit:** n/a (pre-build)

---

### 2026-03-31T00:02 — Decision: Version History — Git commits vs. Snapshot JSON array

| | Git commits | Snapshot JSON array in document file |
|---|---|---|
| Diff computation | git diff — exact, line-level, free | Must implement custom diff algorithm |
| Tooling for manual inspection | git log, git show, git diff | Requires custom tooling |
| Corruption failure mode | One version lost — rest intact | JSON parse error = entire history unreadable |
| Fix path on failure | git fsck, git reflog — standard tools | Custom repair code |
| Storage growth | Text compresses well in git pack files | JSON bloat grows unboundedly |
| Human can edit files directly? | Yes — git tracks the change | Yes, but silently breaks JSON structure |
| Restore semantics | Write old content as new commit (append-only) | Same append behavior required |

**Decision:** Git commits. Diff tooling is free, storage is battle-tested, and failure mode (one history gap) is recoverable. JSON array corruption makes all history unreadable — far worse failure mode.
**Files:** Project documents directory (to be initialized as git repo in Phase 1)
**Impacts:** Version history API endpoints all use git log + git diff. No custom diff engine needed.
**Commit:** n/a (pre-build)

---

### 2026-03-31T00:03 — Decision: Storage Model — Files only vs. Files + SQLite vs. Database only

| | Files + git only | Files + git + SQLite | Database only (Postgres) |
|---|---|---|---|
| Document content | In files | In files | In DB records |
| Structured metadata (calls, edit states, tasks) | No storage — cannot query | SQLite tables | DB tables |
| Query: "all pending proposed edits" | Must scan JSON files — impractical | Single SQL query | Single SQL query |
| Setup complexity | Zero | Low — better-sqlite3 npm package | High — DB server, connection string |
| DB unavailable failure mode | N/A | App falls back to file reads | App is completely down |
| Right for current scale (1 rep, 1 project) | Too limited | Yes | Overkill |

**Decision:** Files + git + SQLite. Files and git handle document content and version history. SQLite handles structured metadata without requiring a server. No over-engineering for current scale.
**Files:** SQLite database file (to be created at server startup in Phase 1)
**Impacts:** Backend must initialize SQLite schema on startup. All call/task/edit state queries go through SQLite.
**Commit:** n/a (pre-build)

---

### 2026-03-31T00:04 — Decision: AI Extraction Output Format — Structured JSON schema vs. Free-form with parsing

| | Structured JSON schema | Free-form with parsing |
|---|---|---|
| Response reliability | Consistent structure; schema validation catches errors | Parsing logic is fragile; edge cases produce silent wrong edits |
| What happens when Claude deviates | JSON parse or schema validation fails; clear error | Parser produces wrong edits; may corrupt files |
| Diff rendering | Exact old_value/new_value available | Must re-derive diff from parsed output |
| Who owns the fix path | We fix the schema or the prompt | We fix the parser and the prompt |
| Extensibility | Add fields to schema; update validation | Update parser and test every edge case again |

**Decision:** Structured JSON schema. The schema is the contract between Claude and our backend. Deviations are caught cleanly at validation rather than propagated as wrong data.

Schema v1: `[{ file_path, field_label, old_value, new_value, confidence, source_quote }]`

**Files:** Proposed edits validation module (to be created in Phase 2)
**Impacts:** Claude system prompt must specify exact JSON schema. All UI diff rendering uses old_value/new_value directly.
**Commit:** n/a (pre-build)

---

### 2026-03-31T00:05 — Blind spot review findings documented

- **Did:** Conducted fresh-perspective blind spot review. Found 8 issues: (1) absolute paths required for git ops, (2) stale frontend in-memory content during direct edits, (3) Claude file path traversal risk, (4) orphaned SQLite rows if proposed-edits.json deleted early, (5) commit message label collision, (6) diff direction ambiguity in version history API, (7) no auth — documented as accepted risk, (8) monolithic script block convention needed.
- **Why:** Mandatory per engineering principles Principle 15. Blind spot review finds what cognitive anchoring hides.
- **Files:** `epochs/01-EPOCHS/epoch-1-happy-path.md` (findings section)
- **Impacts:** Items 1, 2, 3 are critical — specific backend fixes required before Phase 1 is complete. Items 4–8 are implementation conventions.

---

### 2026-03-31T00:06 — Epoch 1 complete, pending human review

- **Did:** Completed full epoch: 5 happy path flows, 14 flow explosion branches, 4 tool decisions with tradeoff tables, 17 failure modes, engineering principles review, blind spot review. Produced HTML deck.
- **Why:** Architecture is converged for Phase 1 scope. Human review is the next required checkpoint.
- **Files:** `epochs/01-EPOCHS/epoch-1-happy-path.md`, `epochs/01-EPOCHS/epoch-1-deck.html`, `epochs/04-STATE.md`, `epochs/05-DECISION-LOG.md`
- **Impacts:** No code written yet. Phase 1 build begins only after human approves the deck.

---

### 2026-03-31T14:00 — Evaluation 2 written: research findings + piecemeal validation plan

- **Did:** Ran proper evaluation: staff engineer subagent critique + 4 web searches + openclaw repo research + Anthropic structured outputs docs. Found 8 material corrections to eval-1. Produced piecemeal validation plan: 8 test scripts in priority order.
- **Why:** Eval-1 was written without web research or subagent critique — not compliant with CLAUDE.md methodology. This corrects that.
- **Key findings:** (1) `output_config.format` closes the structured output question — strictly better than tool_use or string parsing, GA on current models; (2) git commit granularity changed from per-edit to per-call — eliminates index lock race, makes history meaningful; (3) 409 conflict detection is not optional — primary use case creates the race; (4) prompt/model version tracking needed in proposed_edits; (5) Claude API needs timeout + retry with backoff; (6) git index.lock self-healing needed; (7) old_value staleness check before applying edits; (8) openclaw-config validates our file-first approach.
- **Files:** `epochs/01-EPOCHS/eval-2-piecemeal.md`
- **Impacts:** Epoch 2 or Scope Confirmation will incorporate all 8 corrections. Piecemeal test scripts are the next build artifacts.

---

### 2026-03-31T12:00 — Evaluation 1 written: Express explanation + backend system design

- **Did:** Wrote `eval-1-best-practices.md`. Covers: Express vs React in plain English (for a user who hasn't used Express before), full SQLite DDL with CHECK constraints and triggers, error handling architecture (AppError class + asyncHandler + error middleware + operation-level catches), git wrapper implementation, stale-content 409 conflict pattern, Claude API integration with tool_use alternative, in-memory call queue, 6 open questions flagged for human + agent critique.
- **Why:** Between-epoch evaluation is mandatory per CLAUDE.md. User requested focus on rock-solid backend: try/catches everywhere, correct system architecture, DB design. User also requested Express be explained plainly.
- **Files:** `epochs/01-EPOCHS/eval-1-best-practices.md`
- **Impacts:** Eval raises two potentially structural questions: (1) tool_use vs string-parse for Claude API — tool_use is strictly better and may be worth adopting from day one; (2) conflict detection on direct edits — adds frontend complexity, decision deferred to human.

---

<!--
  EXAMPLE ENTRIES (delete these when you start your project):

  ### 2026-03-16T14:00 — Created auth workstream file
  - **Did:** Set up workstream file for authentication module
  - **Why:** Isolated from API workstream — no shared dependencies
  - **Files:** `03-WORKSTREAMS/ws-auth.md`
  - **Impacts:** None

  ### 2026-03-16T14:30 — Chose pg_net triggers over Supabase Webhooks

  | | Supabase Webhooks | pg_net (chosen) |
  |---|---|---|
  | Setup time | 5 min, point-and-click | ~30 min, write SQL |
  | Code ownership | Supabase's code, black box | Our code, version controlled |
  | Debuggability | Can't inspect internals | Full visibility |
  | If it breaks | File a support ticket | We fix it |

  **Decision:** pg_net. Email triggering is critical business logic. We own the fix path.
  **Files:** `supabase/migrations/20260312_triggers.sql`
  **Impacts:** All workstreams using DB triggers
  **Commit:** `abc123`
-->
