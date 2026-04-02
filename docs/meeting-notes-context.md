# Meeting Notes & Pre-Call Context

## What we want

Before or after processing a transcript, the consultant should be able to add free-form notes that get considered alongside the transcript during AI extraction. Examples:

- "She mentioned offhand that they're looking at a competitor — don't capture that, it was sensitive"
- "The date on this transcript is wrong, it was actually March 15"
- "Focus on the floor plan discussion, ignore the small talk at the top"
- "This is a follow-up to the Feb 28 call — Tom is the decision-maker, not Karen"

These notes give the AI context that doesn't appear in the transcript itself.

---

## Two types of notes

### 1. Per-call notes (attached to one specific call)
- Added before submitting the transcript OR after extraction (to refine)
- Stored in `calls.json` alongside the transcript
- Passed to Claude as part of the extraction prompt

### 2. Standing project context (applies to all calls)
- Notes that always apply to this engagement (e.g. "AO is the consultant, JM is the client")
- Stored in a `_context.md` file in the project directory
- Automatically included in every extraction prompt

---

## Implementation plan (not yet built)

### Standing context
- Add `test-data/golden-eagle/_context.md` as a reserved file
- In `inngest_functions.py`, if `_context.md` exists, prepend it to the extraction prompt as `## Standing Context`
- UI: editable in the normal file editor, labeled "Project Context" in the nav

### Per-call notes
- Add a "Notes" textarea to the Process Call modal (below the transcript)
- Store as `call["notes"]` in calls.json
- Pass to Claude in the extraction prompt as `## Consultant Notes\n{notes}`
- Show notes in the call detail view

### Prompt injection
When notes are present, the user message becomes:
```
## Call Transcript
{transcript}

## Consultant Notes
{notes}  ← only if provided

## Standing Context
{_context.md content}  ← only if file exists

## Current Project Files
{files}
```

---

## Status
- [ ] Per-call notes field in modal
- [ ] Store notes in calls.json
- [ ] Pass notes to extraction prompt
- [ ] Standing context file support
- [ ] Show notes in call detail view
