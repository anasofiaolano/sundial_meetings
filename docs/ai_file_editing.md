# AI File Editing — Architecture & Vision

## What we want

After every call, the AI reads the transcript and proposes edits to the project's files — floor plan, people, overview, forms. The rep sees a Cursor-style "Proposed Edits" panel at the bottom of the call view: each affected file listed with inline diffs (green additions, strikethrough removals). They can accept per file or hit "Accept all."

Separately, the rep can also chat with the AI assistant directly and say things like "update Lauren's notes to say she's now leaning toward cedar" — and the AI makes those edits the same way, showing the same proposed-edits UI before writing.

Both triggers (post-call extraction and rep prompt) produce the same output: a list of proposed file edits the rep reviews before committing.

---

## File format: unstructured is fine

Project files (floor plan, people, overview) don't need a special structured schema or field-level history arrays. Plain prose / markdown documents are fine. The AI is perfectly capable of reading an unstructured file, understanding what's in it, and making a targeted edit — just like Claude Code edits source files.

This keeps documents human-readable and editable directly, and doesn't lock us into a rigid schema.

---

## How the AI decides what to edit — learnings from Claude Code source

We read the Claude Code source (`src 2`) to understand how it figures out which files to change. Key findings:

**There is no pre-planned "file list."** The decision is fully emergent from a search → read → edit loop:

1. **Search** — AI uses Glob/Grep-equivalent tools to find candidate files ("which files mention flooring?")
2. **Read** — AI reads the candidates to confirm relevance and see current content
3. **Edit** — AI edits only files it has read; the edit tool errors if you try to edit something you haven't read

The system prompt instructs: *"do not propose changes to code you haven't read — read it first."* FileEditTool enforces this as a hard constraint.

**What this means for us:** We give the AI a small, bounded set of files per project (5–10 documents max: floor plan, people profiles, overview, active forms). After a call, it searches those files for fields touched in the transcript, reads the relevant ones, and proposes targeted edits. The search space is small enough that it doesn't need to scan broadly.

**No explicit planning phase** — the "which files to change" decision comes out of the tool-use sequence itself, guided by the transcript and the AI's understanding of what changed.

---

## Two triggers for file edits

### 1. Post-call extraction (automatic)
After a call is processed:
- AI receives `consolidated.txt` (transcript + screenshots + AI vision summaries)
- AI searches and reads the project's files
- AI produces a proposed-edits list
- Rep sees it at the bottom of the call view — "Proposed Edits · 3 files · 5 changes"
- Rep accepts all or per file

### 2. Rep prompt (manual)
Rep types in the AI chat panel: *"update the floor plan — Lauren switched to cedar flooring"*
- AI reads the floor plan file
- AI produces a proposed edit showing the change
- Same UI: rep sees the diff and accepts

Both flows produce the same proposed-edits UI. Accepting writes the change and commits a new version.

---

## Versioning (see also versioning.md)

Every accepted edit triggers an autocommit — a full snapshot of the file at that moment, labeled with the source (call name or "Rep edit"). This is the version history the rep can browse Google Docs-style.

- Post-call AI edits: version labeled "Mar 25 call"
- Rep-initiated AI edits: version labeled "Ana · Mar 31, 11:42am"
- Rep direct edits (typing in the doc): autocommit on blur, labeled "Ana · Mar 31, 11:45am"

Version history shows inline diffs (green additions, strikethrough deletions) only when browsing history — normal view is always clean.

---

## AI constraints on editing

- **AI cannot add document structure** — no new sections, tables, or boxes. Only content within existing structure. Structure is human-added only.
- **AI must read before editing** — enforced at the tool level
- **AI proposes, rep approves** — no silent writes. Every AI edit goes through the proposed-edits review UI before being committed.
- **Deletions are preserved in history** — if the AI removes something, it's still visible in the version history diff. Nothing is truly lost.

---

## Mockup implementation (current state)

The Mar 25 call in the mockup demonstrates the proposed-edits UI:
- 3 files proposed: Floor Plan, Project Overview, Lauren Thompson
- Per-file accept/skip buttons + "Accept all"
- Green `+` lines for additions, red strikethrough `-` lines for removals
- Monospace diff styling, Cursor-inspired

Version history is implemented on the Floor Plan doc:
- Right panel lists named versions (one per call)
- Clicking a version shows inline diffs vs the prior version
- "Back to current" returns to clean view
