# Evaluation 2 — Research Findings + Piecemeal Validation Plan

**Status:** 📋 Draft — Pending Review
**Created:** 2026-03-31
**Sources:** Staff engineer subagent critique, Anthropic structured outputs docs (direct), web research on better-sqlite3/git/eval frameworks, openclaw-crm + openclaw-config repos
**Supersedes:** eval-1-best-practices.md on all conflicting points

---

## What Eval-1 Got Wrong or Skipped (Required Reading)

Before the piecemeal plan, here are the material corrections from actual research. These change architecture decisions.

### Correction 1: Git commit granularity — commit per CALL, not per edit

**Eval-1 said:** "One git commit per accepted file edit."

**Research finding (staff engineer):** This creates a noise-filled git log (200 one-line commits after a few months), no git-level grouping by call, and a `.git/index.lock` race condition under rapid accepts (process killed mid-commit → lockfile blocks all subsequent commits silently until manually deleted).

**Corrected design:**
- Commit once per CALL: when rep clicks "Accept all" or finishes resolving all edits from a call, one batch commit with message `call.label`
- If rep accepts one file at a time across multiple sessions, stage files and commit when the call is "fully resolved" (all proposed_edits for that call_id are accepted or skipped)
- For edit-level undo: store `previous_content` as a TEXT blob in the `proposed_edits` row. Restoring = writing the blob back + new commit. Git for call-level history; SQLite for field-level rollback.

**Impact:** Version history panel still works (one commit per call = clean git log). Edit-level undo is explicit via "restore" button in the proposed edits history view.

### Correction 2: Use `output_config.format` — not tool_use, not string parsing

**Eval-1 said:** "tool_use is better than string parsing — open question whether to adopt."

**Research finding (Anthropic docs, direct):** There is now a third option that's strictly better than both:

```javascript
await client.messages.create({
  model: 'claude-opus-4-6',
  max_tokens: 4096,
  output_config: {
    format: {
      type: 'json_schema',
      schema: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            file_path:    { type: 'string' },
            field_label:  { type: 'string' },
            old_value:    { type: 'string' },
            new_value:    { type: 'string' },
            confidence:   { type: 'string', enum: ['high', 'medium', 'low'] },
            source_quote: { type: 'string' }
          },
          required: ['file_path', 'field_label', 'old_value', 'new_value', 'confidence', 'source_quote'],
          additionalProperties: false
        }
      }
    }
  },
  messages: [{ role: 'user', content: userMessage }]
})
// response.content[0].text is ALWAYS valid JSON matching the schema
// No JSON.parse() errors. No markdown fences. No retries for schema violations.
```

`output_config.format` uses constrained decoding at the token level — Claude literally cannot generate invalid JSON. It's GA on Opus 4.6 and Sonnet 4.6 (our target models). No beta headers needed.

**This closes the "tool_use vs string parsing" question permanently.** Use `output_config.format`.

### Correction 3: 409 conflict detection is not optional

**Eval-1 said:** "Open question — start with last-write-wins?"

**Research finding (staff engineer):** The primary use case creates the race condition. Rep is reviewing proposed edits AND typing in a contenteditable field at the same time — that's the core UX. Last-write-wins silently drops whichever save arrived second. This is not a theoretical edge case.

**Corrected design:** Implement checksum-based 409 from day one. Client sends `X-Content-Checksum` header with every save. Server computes checksum of current file, compares, returns 409 with `currentContent` if mismatch. Frontend shows: "This file was updated. [View diff] [Overwrite] [Discard]."

### Correction 4: Add `prompt_version` and `model_version` to proposed_edits

**Eval-1 missed:** No record of which Claude prompt generated which extraction.

**Research finding (staff engineer):** When extractions are wrong, you need to know what prompt was used. Six months in, you can't reproduce the failure. This is basic audit trail hygiene.

**Corrected schema addition:**
```sql
ALTER TABLE proposed_edits ADD COLUMN prompt_version TEXT;  -- e.g., "extraction-v1"
ALTER TABLE proposed_edits ADD COLUMN model_version TEXT;   -- e.g., "claude-opus-4-6"
```

### Correction 5: Claude API call timeout + retry with backoff

**Eval-1 said:** "In-memory queue, fail to extraction_failed on error."

**Research finding (staff engineer):** No timeout on the Claude API call means a hanging call blocks the in-memory queue indefinitely. No retry with backoff means a 429 rate limit error produces `extraction_failed` when it should produce `retrying in 15s`.

**Corrected design:**
```javascript
// Wrap every Claude API call with a timeout + retry
async function callClaudeWithRetry(params, { timeout = 60_000, maxRetries = 3 } = {}) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await client.messages.create(params, { signal: controller.signal })
      clearTimeout(timer)
      return response
    } catch (err) {
      clearTimeout(timer)
      const isRetryable = err.status === 429 || err.status === 529 || err.name === 'AbortError'
      if (!isRetryable || attempt === maxRetries) throw err
      const backoff = Math.min(2 ** attempt * 1000, 30_000)  // 2s, 4s, 8s... cap at 30s
      await new Promise(r => setTimeout(r, backoff))
    }
  }
}
```

### Correction 6: Add `previous_content` to proposed_edits + stale old_value detection

**Eval-1 missed:** If rep directly edits a file and then accepts a proposed edit for the same file, the `old_value` in the proposed edit no longer matches what's on disk. The write happens anyway — silently writing the wrong replacement.

**Corrected design:** On accept, before writing: verify `old_value` still appears in the current file content. If not: return a specific error code `OLD_VALUE_MISMATCH`, surface it to the rep: "The file changed since this edit was proposed. The expected content no longer exists. [View current file] [Skip this edit]."

### Correction 7: Git index lock self-healing

**Eval-1 missed entirely.**

`.git/index.lock` is left behind when a git process is killed mid-operation (OOM kill, server restart). Every subsequent git command fails with `fatal: Unable to create '.git/index.lock': File exists`. The application logs `GIT_COMMIT_FAILED` forever. Recovery requires manual deletion.

**Fix:** In the git wrapper, detect this specific error and self-heal:
```javascript
if (stderr.includes('index.lock') && stderr.includes('File exists')) {
  // Safe to delete: if we're here, no git operation is running (we're in the error handler)
  const lockPath = path.join(cwd, '.git', 'index.lock')
  try {
    await fs.unlink(lockPath)
    // Retry the original command once
    return await runGit(cwd, args)
  } catch (unlinkErr) {
    throw new AppError('git index lock stuck — manual recovery needed', 500, 'GIT_INDEX_LOCK')
  }
}
```

---

## Openclaw Research — Relevant Prior Art

Two repos worth knowing:

**openclaw-config (TechNickAI):** "Prose over config" — all knowledge in markdown + git. Three-tier memory architecture:
- Tier 1: always-loaded summary (~100 lines)
- Tier 2: daily context files (raw observations)
- Tier 3: structured knowledge by `people/`, `projects/`, `topics/`, `decisions/`

This is essentially the same architecture we're building for the CRM. Key learning: **no database**. Everything is a file. AI reasons through natural language in the files. This validates our file-first approach and suggests we may not even need SQLite for document content — but we do need it for call tracking and edit state.

**openclaw-crm (giorgosn):** Uses a Typed EAV (Entity-Attribute-Value) pattern with PostgreSQL + Next.js. Much heavier than what we're building. Takeaway: they went DB-first and lost human-readability. We're going file-first — right call.

---

## Piecemeal Validation Plan

The whole system is 8 distinct pieces. Each should be validated in isolation before integration. Below: what each piece is, what to test, what success looks like, and what order.

### Piece 1 — AI Extraction Script (HIGHEST PRIORITY)

**What it is:** The core intelligence loop. Takes MD project files + a consolidated.txt → calls Claude → returns JSON edit proposals.

**Why first:** If this doesn't produce reliable, accurate edits, nothing else matters. Validate before building ANY infrastructure.

**What to build:** `scripts/test-extraction.js`

```
Input:  /test-data/golden-eagle/floor-plan.md
        /test-data/golden-eagle/people/lauren-thompson.md
        /test-data/golden-eagle/project-overview.md
        /test-data/transcripts/mar-25-call.txt   ← fake but realistic transcript

Output: prints the JSON edit proposals to stdout
        prints which file_paths Claude identified
        prints confidence levels
        prints source_quotes
```

**What to tune:**
- System prompt quality: does Claude identify only explicit changes, or does it hallucinate?
- Does it respect the "content only, no structure" constraint?
- Does `output_config.format` produce clean JSON every time?
- What happens with an empty transcript (no changes)? Does it return `[]`?
- What happens with a very long transcript + large files? Does it hit context limits?

**Success criteria:**
- Given a transcript that mentions 3 specific changes, Claude proposes exactly those 3 changes (not 2, not 5)
- `file_path` values are always from the provided files list (no hallucination)
- `old_value` matches actual text in the file (verifiable)
- `confidence` is appropriately calibrated (explicit statement → high, implied → medium)
- Output is valid JSON matching schema on every run (10/10 runs minimum)

**What to seed (test data needed before running):**
- `floor-plan.md`: realistic Golden Eagle floor plan with actual fields
- `lauren-thompson.md`: people profile with role, notes, concerns
- `project-overview.md`: stage, value, blockers, next action
- `mar-25-call.txt`: fake transcript with 3-4 clear changes mentioned

---

### Piece 2 — Git Wrapper

**What it is:** Node.js module that wraps all git operations: init, add, commit, log, diff.

**What to build:** `scripts/test-git.js`

```
Test 1: Init a temp repo, commit a file, verify commit appears in git log
Test 2: Commit two versions of a file, run git diff, verify diff output is correct
Test 3: Simulate a git index lock, verify self-healing works
Test 4: Commit with a message containing special characters (apostrophes, quotes)
Test 5: Run git on a non-git directory, verify error is caught and typed correctly
Test 6: Verify absolute paths are always used (no cwd() dependency)
```

**Success criteria:**
- All 6 tests pass deterministically
- Index lock self-healing works (manually place a lock file, verify it's cleared and commit retries)
- Every error produces a named AppError code (no raw git stderr leaking to caller)

---

### Piece 3 — SQLite Schema + Constraint Validation

**What it is:** Create the database, verify all CHECK constraints fire correctly, verify triggers work.

**What to build:** `scripts/test-db.js`

```
Test 1: Insert a call with valid status — succeeds
Test 2: Insert a call with invalid status ("done") — throws SQLITE_CONSTRAINT_CHECK
        → verify this maps to a readable AppError, not raw SQLite error
Test 3: Insert a proposed_edit with status=accepted and resolved_at=null — succeeds
Test 4: Insert a proposed_edit with status=pending and resolved_at set — trigger fires, rejects
Test 5: Insert a proposed_edit with status=extraction_ready and error_msg set — trigger fires, rejects
Test 6: Verify WAL mode is active: db.pragma('journal_mode') returns 'wal'
Test 7: Verify foreign_keys are ON: db.pragma('foreign_keys') returns 1
```

**Success criteria:**
- All 7 tests pass
- Every constraint violation produces a typed AppError (not a raw `SQLITE_CONSTRAINT_CHECK` with SQLite's generic message)

---

### Piece 4 — File Write + Path Traversal Security

**What it is:** The file write utility: accepts a project dir + relative path, validates traversal, writes content.

**What to build:** `scripts/test-file-write.js`

```
Test 1: Write a file within the project dir — succeeds
Test 2: Write a file with path "../../server.js" — throws PATH_TRAVERSAL
Test 3: Write a file with path "../sibling-project/file.md" — throws PATH_TRAVERSAL
Test 4: Write a file with a valid path containing subdirectory ("people/lauren.md") — succeeds
Test 5: Write to a full disk (can simulate by mocking fs.writeFile to throw ENOSPC) — throws DISK_FULL
Test 6: Write to a permission-denied path — throws FILE_PERMISSION
```

**Success criteria:** All 6 tests pass. No path traversal possible through any input variant.

---

### Piece 5 — Diff Rendering

**What it is:** Takes git diff output (unified diff format) → produces the `{added: [...], removed: [...]}` structure the frontend uses for inline diff display.

**Why piecemeal:** If the diff parser is wrong, version history shows incorrect diffs. Easy to test in complete isolation (just string parsing).

**What to build:** `scripts/test-diff-parser.js`

```
Test 1: Single field value change → correct added/removed lines
Test 2: Addition with no removal (new content added) → only added lines
Test 3: Deletion with no addition → only removed lines
Test 4: Multi-line change in notes section → all affected lines captured
Test 5: Empty diff (no changes) → empty result, no errors
Test 6: Binary file in diff output (shouldn't happen, but handle gracefully)
```

**Success criteria:** All 6 tests pass. Diff rendering matches what the mockup currently shows.

---

### Piece 6 — Old_value Matching (Apply Edit Logic)

**What it is:** Before accepting a proposed edit, verify `old_value` still exists in the current file. If found, replace with `new_value`. If not found, return `OLD_VALUE_MISMATCH`.

**This is the critical correctness piece.** The replace logic must:
- Find the right instance of `old_value` (what if it appears twice in the file?)
- Handle whitespace/newline sensitivity
- Not corrupt surrounding content

**What to build:** `scripts/test-apply-edit.js`

```
Test 1: old_value matches exactly once — correct replacement
Test 2: old_value appears twice — surface ambiguity, don't silently replace wrong instance
Test 3: old_value not found (file changed since extraction) — returns OLD_VALUE_MISMATCH
Test 4: old_value with trailing/leading whitespace differences — configurable: strict vs trimmed match
Test 5: Replacement that changes content length (longer new_value) — surrounding content preserved
Test 6: old_value is empty string (new content, no prior value) — append behavior
```

🚨 **HUMAN EVALUATE:** Test 2 (old_value appears twice) — should we fail or should we replace the first occurrence? The staff engineer flagged this. I lean toward failing with a warning, letting the rep decide. Open to pushback.

**Success criteria:** All 6 tests pass. No silent incorrect replacements.

---

### Piece 7 — Checksum-Based Conflict Detection

**What it is:** Client sends a checksum of the file content it started with. Server compares to current file before writing. 409 if mismatch.

**What to build:** `scripts/test-conflict.js`

```
Test 1: Client sends current checksum → write succeeds
Test 2: Client sends stale checksum (file changed on disk) → 409 returned with current content
Test 3: Client sends no checksum → write succeeds (backward compat: checksum is optional)
Test 4: Two concurrent writes with same starting checksum → second one gets 409
```

**Success criteria:** All 4 tests pass. No data loss, no silent overwrites.

---

### Piece 8 — End-to-End Smoke Test (After All Pieces Pass)

Only once pieces 1–7 all pass individually:

```
1. Create a temp project directory with seed MD files
2. Initialize git repo in it
3. Run AI extraction on a test transcript
4. Verify proposed edits JSON matches expected output
5. Accept one edit via the accept endpoint
6. Verify file on disk is updated correctly
7. Verify git commit exists with correct label
8. Verify SQLite proposed_edit row is updated to accepted
9. Fetch version history via API
10. Verify diff endpoint returns correct diff for that commit
```

---

## Recommended Build Order

| Order | Piece | Why This Order |
|-------|-------|----------------|
| 1 | AI Extraction Script | Validates the core intelligence before building infrastructure around it |
| 2 | SQLite Schema | Cheap to set up, catches constraint bugs early, needed by everything else |
| 3 | Git Wrapper | Core infrastructure. Self-healing index lock test is critical before any commit logic |
| 4 | File Write + Security | Needed before any edit acceptance |
| 5 | Apply Edit Logic | The correctness of edit application must be proven before integration |
| 6 | Diff Rendering | Can run in parallel with 4–5 |
| 7 | Conflict Detection | Needed before any frontend integration |
| 8 | Smoke Test | Only after all above pass |

**Rule:** Do not wire pieces together until each passes its standalone tests. Debugging integrated failures is 10x harder than debugging isolated failures.

---

## Other Piecemeal Things I'd Validate (Beyond User's Original Ask)

These are additional isolation points I'd add to the test suite that aren't obvious but will save significant debugging time:

**A. Token budget check before API call.** Before calling Claude with project files + transcript, count tokens and fail fast if over the budget (leave 2K tokens for output). The alternative is a context-length error mid-flight. Token counting: `client.countTokens()` is a cheap API call.

**B. Git repo health check on startup.** Run `git fsck --no-full` on each project repo at server startup. If it fails, mark the project as `git_health: degraded` in SQLite. The rep sees a warning: "Version history may be incomplete." File writes still work. Nobody is blocked, but nobody is silently losing history.

**C. WAL checkpoint management.** After every N commits (say, 100), run `db.pragma('wal_checkpoint(RESTART)')` to prevent the WAL file from growing unboundedly. This is a one-liner but needs to be triggered somewhere — startup is fine for Phase 1.

**D. proposed-edits.json vs SQLite consistency check (startup).** On server start: query SQLite for any calls with `status=extraction_ready` where the `proposed-edits.json` file doesn't exist on disk. These are orphaned — mark them `extraction_failed`. Vice versa: if `proposed-edits.json` exists but there's no corresponding SQLite row in `extraction_ready` state, log a warning and create the row. These checks are < 10 lines each and prevent invisible data inconsistencies.

**E. Recoverable vs non-recoverable error classification.** Every AppError needs a `recoverable` boolean and a `userAction` string:
- `GIT_COMMIT_FAILED` → recoverable: false, userAction: "File saved. Run 'git add . && git commit' in your project folder to restore version history."
- `CLAUDE_API_FAILED` → recoverable: true, userAction: "Try re-processing this call."
- `PATH_TRAVERSAL` → recoverable: false, userAction: "Contact support."
- `OLD_VALUE_MISMATCH` → recoverable: true, userAction: "Skip this edit or view the current file."

The frontend renders these directly in the error UI rather than generic "something went wrong."

---

## What This Changes in the Architecture

| Area | Old | New |
|------|-----|-----|
| Git commit granularity | One commit per accepted file edit | One commit per resolved call (all edits accepted/skipped) |
| Structured output API | tool_use (open question) | `output_config.format` with json_schema (closed) |
| Conflict detection | "Start with last-write-wins" | 409 + checksum from day one |
| Proposed_edits schema | No prompt/model tracking | `prompt_version`, `model_version` columns |
| Claude call timeout | Not specified | 60s timeout, retry with exponential backoff × 3 |
| Git index lock | Not handled | Self-healing: detect, delete lock, retry |
| Old_value staleness | Silent incorrect write | Server-side verification before applying edit |
| Error surface to rep | Generic "failed" | Typed: recoverable bool + userAction string |

---

---

## Addendum — Piecemeal Testing Research Agent Findings

*Appended from second subagent that completed after initial draft.*

### A. Adopt SEARCH/REPLACE blocks (Aider pattern) instead of bare `new_value`

**Finding:** Aider (the most mature LLM file editor, `github.com/paul-gauthier/aider`) uses a SEARCH/REPLACE block format for edits. The LLM emits:

```
<<<<<<< SEARCH
Foundation Height: 9'
=======
Foundation Height: 14'
>>>>>>> REPLACE
```

The write layer applies this deterministically. This is more reliable than just storing `new_value` and trying to splice it in because:
- The apply logic is unambiguous: find exact SEARCH text, replace with REPLACE text
- The diff renders cleanly for the proposed-edits UI (exactly what we want)
- The LLM is incentivized to produce minimal diffs, not rewrite surrounding content

**Impact on our schema:** The proposed-edits JSON carries `old_value` + `new_value` already. The write layer should use `old_value` as the SEARCH block and `new_value` as the REPLACE block — same data, explicit application logic. This is what Piece 6 (Apply Edit Logic) tests.

### B. Three-layer eval pyramid — don't start at Layer 3

**Finding:** Most teams over-invest in LLM-as-judge eval before Layer 1 is solid. The correct order:

| Layer | What | How | When |
|-------|------|-----|------|
| 1 | Schema conformance | `jsonschema` validate | Every run, day 1 |
| 2 | Golden-file regression | Fixture input → expected output diff | Once 3 fixtures exist |
| 3 | LLM-as-judge quality | Second Claude call scoring output | Batch only, not CI |

Don't run Layer 3 until Layer 1 is 100%. A failing schema conformance test is not a failing quality eval — fix Layer 1 first.

**Eval framework recommendation: promptfoo** (open source, runs locally, native Anthropic support). Better fit than LangSmith (too heavy) or manual pytest alone (fine but promptfoo adds structured reporting). Skip for Phase 1 — a simple pytest fixture set is sufficient. Add promptfoo in Phase 2 when you have real call data to evaluate against.

### C. "Lost in the middle" degradation — chunk long transcripts

**Finding:** Documented in Liu et al. (2023): LLMs perform worse on content in the middle of long contexts. For a mature Golden Eagle project (50-100KB of project files + 20-30KB transcript = 70-130KB input / 17K-32K tokens), this will affect extraction quality on long calls.

**Mitigation options:**
1. **Chunk by topic** (preferred): group transcript segments by topic (floor plan, pricing, contacts), run one extraction call per topic group. Each call is shorter and focused.
2. **Summarize first, extract second**: run a summarization pass ("what changed in this call, as bullet points"), then run extraction on the bullets. Two cheap calls beat one degraded call.
3. **Prefill with key moments**: during `consolidated.txt` assembly (Stage D), add a "Key moments" section at the top from Claude Vision's `discussion_relevance` outputs.

Add a token budget check to Piece 1 test harness: `client.countTokens()` before every extraction call.

### D. Add the null-case test

**Finding:** The first thing to break when prompts drift is false positives — the system proposes edits when nothing changed. Add an explicit fixture where `consolidated.txt` contains NO changes to project files (e.g., a scheduling call or small talk) and assert the proposed edits list is empty.

This belongs in Piece 1 as Test 6:
```
Test 6: consolidated.txt with no actionable changes → returns [] (not hallucinated edits)
```

### E. Build fixture consolidated.txt files by hand first

**Finding:** Don't wait for the full pipeline (Stages A–D) to generate fixtures. Write 3–5 `consolidated.txt` files by hand from notes or a real transcript. This lets you test Stage E (Claude extraction) on day 1 without building ffmpeg, Claude Vision, or the file assembly pipeline.

This is already implied in the Piece 1 test plan but worth making explicit: the test data files needed for Piece 1 are the most valuable thing to create immediately.

---

## Next Steps

- [ ] Seed test data: create realistic Golden Eagle MD files for `test-data/golden-eagle/`
- [ ] Write 3 fixture `consolidated.txt` files by hand (don't wait for the pipeline)
- [ ] Build and run Piece 1 (AI extraction script) — this is the most valuable thing to validate first
- [ ] Based on Piece 1 results: tune system prompt, decide on context selection strategy (chunk by topic vs. summarize first)
- [ ] Build remaining pieces in order
- [ ] ⏸ CHECKPOINT: Human reviews this document before we proceed to Scope Confirmation or Epoch 2
