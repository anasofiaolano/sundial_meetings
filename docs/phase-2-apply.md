# Phase 2: Apply Edit Logic

Takes proposed edits from the extraction phase and writes them back to project files.

**Status:** Built. Tests pending.

---

## What was built

| File | Purpose |
|------|---------|
| `scripts/phase-2/apply-edits.js` | Core apply module — `applyBatch()` |
| `scripts/phase-2/test-apply.js` | Fixture-based test runner |
| `test-data/phase-2/` | Fixtures: before/edits/after files for each test case |

---

## How to run

```bash
node scripts/phase-2/test-apply.js
```

---

## Design decisions

All patterns copied from Claude Code's `FileEditTool` (`src/tools/FileEditTool/`).

---

### 1. Quote normalization

**Decision:** Before matching `old_value` in a file, normalize curly quotes → straight quotes on both sides.

**Why:** Claude sometimes outputs `"text"` (straight) when the file contains `"text"` (curly). Without normalization, the match fails silently and the edit is never applied. Claude Code handles this in `findActualString()` and `normalizeQuotes()`.

**Implementation:** Try exact match first. If not found, normalize both sides and retry. If the match was via normalization, apply the same curly-quote style to `new_value` (`preserveQuoteStyle`) so the file's typography is preserved.

---

### 2. Read-state tracking + gating

**Decision:** Every file must be explicitly read (via `trackRead()`) before it can be edited. Attempting to edit an unread file throws immediately.

**Why:** This is Claude Code's `readFileState` pattern (FileEditTool.ts line 275). The edit logic needs the file content in memory to compute `old_value` matches. Requiring an explicit read makes the dependency visible and prevents edits based on stale or assumed content.

**Implementation:** `readFileState` map: `absolutePath → { content, timestamp }`. `trackRead()` reads the file, normalizes line endings, and records the mtime. `applyBatch()` calls `loadProjectFiles()` which reads all project files upfront.

---

### 3. Staleness check

**Decision:** Immediately before writing a file, compare the file's current mtime to the mtime recorded when we read it. If the file was modified on disk since our read, abort that file's write.

**Why:** Claude Code does this check twice — in `validateInput` and again in `call()` (FileEditTool.ts line 452). The second check is the important one: it catches the window between validation and execution. For us, it catches the case where a file is modified between extraction and apply (e.g., user edits directly, another process writes).

**Failure mode:** The file's edits are moved to `failed` with `FILE_MODIFIED_SINCE_READ`. The file is not written. No data loss.

---

### 4. Atomicity — synchronous read + write

**Decision:** The staleness check and file write are done synchronously (`fs.statSync`, `fs.writeFileSync`). No `await` between them.

**Why:** In async JavaScript, every `await` yields to the event loop — other code can run in that gap. If we `await` between the staleness check and the write, a concurrent request could modify the file in that window and we'd overwrite it without knowing. Using synchronous fs calls makes the critical section uninterruptible. Node.js is single-threaded: sync code cannot be interrupted by other JS.

**Pattern:**
```javascript
// All async work happens before this point (Claude API calls, etc.)
// From here: synchronous only — no awaits
for (const [path, content] of pendingWrites) {
  const { mtimeMs } = fs.statSync(path)          // sync
  if (mtimeMs > state.timestamp) { skip }
  fs.writeFileSync(path, content, 'utf8')         // sync
}
// Back to async world for git commit
```

This matters now (single-user script) and matters a lot when this becomes an Express server handling concurrent requests.

---

### 5. Multi-edit safety (old_value ⊂ previous new_value)

**Decision:** When applying multiple edits to the same file, check that each edit's `old_value` is not a substring of any previously applied `new_value`. If it is, fail that edit with `OLD_VALUE_SUBSET_OF_PREVIOUS_NEW_VALUE`.

**Why:** Copied from Claude Code's `getPatchForEdits()` (utils.ts line 302). Consider: edit 1 replaces `"(no notes yet)"` with `"Jay is the owner. (no notes yet) See below."`. Edit 2 has `old_value = "(no notes yet)"`. Now `(no notes yet)` appears in the new content from edit 1 — but edit 2 was written against the *original* file. Applying it would produce wrong results. The check catches this before it causes corruption.

---

### 6. Duplicate match handling

**Decision:** Count occurrences of `old_value` using `content.split(old_value).length - 1`. If > 1: error `AMBIGUOUS_MATCH`, trigger retry via `clarifyOldValue`.

**Why:** Copied from Claude Code (FileEditTool.ts line 329). A silent replace of the wrong occurrence would corrupt the file with no indication. Explicit failure + retry is always better than silent wrong behavior.

---

### 7. clarifyOldValue retry

**Decision:** On `OLD_VALUE_NOT_FOUND` or `AMBIGUOUS_MATCH`, call Haiku once with the full transcript + file content + the broken edit. Ask only for a revised `old_value`. Use the original `new_value` unchanged.

**Why:** The full transcript gives Haiku the context to understand *what* was being changed and *where* in the file it belongs. The source_quote alone isn't enough — the surrounding conversation makes the intent clear.

**Model:** `claude-haiku-4-5-20251001` — this is a simple retrieval task (find the right span of text), not a reasoning task. Haiku is fast and cheap for this.

**Safety:** After Haiku returns a revised `old_value`, we sanity-check it ourselves: must exist in the file, must appear exactly once. If either check fails, we return `null` and let `applyBatch` mark the edit as failed for human review.

**One retry only:** `retrying = true` flag prevents infinite loops. If the retry also fails, the edit goes to the failed pile.

---

### 8. Git commit per call

**Decision:** After writing all files, commit with message `call: <transcript-name> — N edits applied`.

**Why:** One commit per call makes `git log` meaningful — each entry is a real event (a call happened, these files changed). Per-edit commits would pollute history. Batching all calls into one commit would lose granularity. Per-call is the right level. From eval-2: "one commit per call eliminates the git index.lock race and makes history meaningful."

**Non-fatal:** If git isn't initialized or the commit fails, we log a warning and continue. The file writes already succeeded — the git layer is auditing, not required for correctness.

---

## Test fixtures

| Fixture | Tests |
|---------|-------|
| F1 — Clean replacement | `(no notes yet)` → real content. Happy path. |
| F2 — Augmentation | Existing sentence + new content appended. Old content preserved. |
| F3 — old_value not found | Error returned. File byte-identical to before. |
| F4 — Duplicate old_value | Ambiguous match. Error returned. File unchanged. |
| F6 — Sequential edits | 3 edits each building on the previous. Final state matches expected. |
