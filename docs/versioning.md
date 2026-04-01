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
