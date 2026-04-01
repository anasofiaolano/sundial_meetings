# Versioning & Document History

## Desired end state

Every document in the CRM (floor plan, project details, people) has a full version history. When you click "Version history" (top right of any doc), a right panel opens showing named versions tied to calls, AI extractions, and user edits. Clicking a version shows the document with inline diffs — Google Docs tracked-changes style:

- **Added** content: green highlight
- **Deleted** content: strikethrough in muted color
- Works on both structured fields and free-form notes/bullet points

---

## What triggers a new version

| Trigger | Who | Behavior |
|---|---|---|
| Post-call AI extraction | AI | New version committed automatically, labeled with the call (e.g. "Mar 10 call") |
| User edits a field or note | Rep | Autocommit on blur/save — no manual action needed |
| Manual save | Rep | Explicit "save version" if needed (optional) |

**Key constraint:** AI can only append. It never deletes prior content — deletions are shown as strikethroughs in the diff, and the old value is always preserved in history.

**Second constraint:** AI cannot add structural document elements (tables, sections, boxes, etc.) — only content within existing elements. Structure can only be added by a human user (e.g. inserting a table manually). Diffs (strikethroughs + green highlights) are only visible when browsing version history — the normal view always looks clean.

---

## How diffs work

Each version is a full snapshot of the document at that point in time (not a diff itself — diffs are computed on the fly when you select a version).

When you select version V, the view shows:
- The document as it was AT version V
- With inline diffs showing what changed FROM the version before V (so you see "what happened in this version")
- Banner at top: "Showing changes made in [V] vs [V-1]"

---

## Document types this applies to

- **Floor plan** — fields + notes (implemented in mockup as proof of concept)
- **Project details / Overview** — stage, value, blockers, next action
- **People** — contact info, role, notes, sentiment

---

## Why not other approaches

- **Confirm Y/N before AI writes** — too much friction for reps
- **Append-only markdown** — no clean current value, hard to render
- **Field-level history arrays** — rejected; unstructured docs are fine, AI can edit them just like source code. See `ai_file_editing.md`.

## Related

See `ai_file_editing.md` for how the AI decides what to edit, the two triggers (post-call vs. rep prompt), and Claude Code source learnings.

---

## Autocommit implementation notes (for when we build the real backend)

- On user blur of any editable field or note: debounce ~2s then commit snapshot to disk
- Version label: "You · [date + time]"
- On AI extraction completing: commit immediately, label with call name
- Store versions as append-only JSON array in the project file — never rewrite history
- "Restore this version" = write that snapshot as a new current version (not overwrite — always append)

---

## Current implementation plan (dogfood server)

### Two-layer model

| Layer | Trigger | Git commit? | Visible in history? |
|-------|---------|-------------|---------------------|
| **Autosave** | 2s after last keystroke | No | No — just data safety |
| **Checkpoint** | Cmd+S, pre-AI, post-AI, named | Yes | Yes |

### Checkpoint triggers

| Event | Commit message | Protected? |
|-------|---------------|------------|
| AI batch about to apply | `snapshot: before <call name>` | Yes — rollback point |
| AI batch finishes | `call: <call name> — N edits applied` | Yes |
| User hits Cmd+S | `checkpoint: <file>` | No (prunable) |
| User names a version | user-supplied label | Yes — forever |

### Retention policy (not yet implemented)
- Auto-checkpoints: up to **100 revisions** or **90 days**, whichever is greater
- Named/protected versions: **kept forever**
- Every entry shows age (e.g. "3d ago") so approaching-90-day entries are visible

### Named versions
Stored in `test-data/named-versions.json`:
```json
[{ "hash": "abc1234", "name": "Post-discovery call", "created": "2026-04-01T..." }]
```

### Implementation order
1. ✅ Post-AI git commit (already in `applyBatch`)
2. [ ] Pre-AI snapshot — commit in `/api/apply` before `applyBatch` runs
3. [ ] Autosave — debounced disk write in edit mode, no git
4. [ ] Cmd+S checkpoint — git commit, replaces Save button
5. [ ] Structured `/api/history` — age, type, named flag per entry
6. [ ] Named versions — `/api/protect-version` + `named-versions.json`
7. [ ] Age display in version history panel
8. [ ] Pruning (future)

### Research basis
Figma (30-min autosave checkpoints, named versions forever), Notion (10-min active /
2-min idle session end), Cursor (checkpoint before every AI edit), Google Drive
(100 revisions / 30 days — we use 90 days).
