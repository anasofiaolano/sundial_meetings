# Plan: Dogfood Pipeline + Version History

## What We're Building

Two things that connect:

1. **Screenshot extraction pipeline** — adapt `extract_screenshots.ipynb` for your upcoming discovery calls with Golden Eagle sales reps. After each call: MP4 + transcript → screenshots at every timestamp → deduplicated frames → paired transcript segments + Claude vision analysis → fed into the CRM mockup.

2. **Field-level version history** — every editable field in the CRM mockup shows a history log of every change: who changed it, when, and which call or document was the source. Matches the screenshot you shared (value → CURRENT + prior versions with timestamps, authors, and source doc tags).

---

## Part 1 — Screenshot Extraction Pipeline for Discovery Calls

### What the existing notebook does

```
MP4 recording + transcript.txt
  → parse transcript into timestamped segments
  → extract one frame per timestamp via ffmpeg
  → deduplicate near-identical frames (pixel diff < threshold)
  → for each saved frame:
      screenshot_HH-MM-SS.jpg   ← the frame
      screenshot_HH-MM-SS.txt   ← transcript segments that overlap this window
      screenshot_HH-MM-SS.json  ← Claude vision: is_form? title? fields? values?
  → consolidated.txt            ← all three merged, in order
```

On the test recording: 130 timestamps → 39 unique frames (91 duplicates skipped). Each frame got a `.json` with Claude's form analysis. Works.

### What needs to change for discovery calls

The current notebook was built for a **CRM review meeting** — shared screen showing forms. Discovery calls with sales reps will have a **different screen share profile**:

| Aspect | CRM review (current) | Discovery calls (new) |
|---|---|---|
| Screen content | Forms being filled in | Floor plans, spec sheets, pricing PDFs, browser |
| Transcript format | MS Teams export (Name + 2+ spaces + timestamp) | Same format — no change needed |
| Claude prompt | Extracts form fields + values | Needs a new prompt: what's on screen + what's being discussed |
| Output use | Consolidated review doc | Feed into CRM mockup call views |
| DIFF_THRESHOLD | 5 (tight, right for forms) | 5–10 (screen share content, probably fine) |

### Changes to make

**1. New Claude vision prompt for discovery calls**

Replace `FORM_ANALYSIS_PROMPT` with a discovery-call-aware prompt:

```
Analyze this screenshot from a sales discovery call.

Return ONLY valid JSON:
{
  "screen_type": "floor_plan | pricing_sheet | spec_doc | browser | slides | blank | other",
  "title": "document or page title if visible, or null",
  "key_content": "1-2 sentence summary of what's on screen",
  "extracted_data": {
    // if floor_plan: { plan_name, sq_footage, bedrooms, notable_features }
    // if pricing_sheet: { line_items: [{label, value}] }
    // if spec_doc: { form_name, visible_fields: [{label, value}] }
    // otherwise: {}
  },
  "discussion_relevance": "how this screen relates to the transcript segment, or null"
}
```

**2. Configuration for Golden Eagle calls**

```python
VIDEO_PATH       = "calls/YYYY-MM-DD_golden_eagle_discovery.mp4"
TRANSCRIPT_PATH  = "calls/YYYY-MM-DD_transcript.txt"
OUTPUT_DIR       = "calls/YYYY-MM-DD_screenshots"
START_TIME       = "0:00"
END_TIME         = None       # process full call
DIFF_THRESHOLD   = 8          # slightly looser for mixed screen content
```

**3. Output → CRM mockup**

After the pipeline runs, the per-call screenshots and transcript segments map directly into the call view in the mockup:

- Screenshots → shown in the call view as a scrollable filmstrip (one thumbnail per saved frame, click to expand)
- Transcript segments → already in the call view as the Transcript section
- `consolidated.txt` → source of truth for post-call AI extraction (same pipeline we designed in `crm_update/PLAN.md`)

### File structure (per call)

```
golden_eagle/
  calls/
    2026-04-01_thompson_discovery/
      recording.mp4
      transcript.txt
      screenshots/
        screenshot_00-05-30.jpg
        screenshot_00-05-30.txt
        screenshot_00-05-30.json
        ...
        consolidated.txt
```

---

## Part 2 — Field-Level Version History in the CRM Mockup

### What it is

Every editable field shows a history log directly inline — visible when you hover or expand. Matches the screenshot shared:

```
Foundation Height    [14']    [1]    [$ Adj]    [Note]

  FOUNDATION_HEIGHT — HISTORY
  14'          CURRENT    Mar 30 9:25 PM · Marcus Torres
  customer change          Mar 30 9:25 PM · Marcus Torres · customer change       SA-208 R3
  9'                       Feb 10 · Sales                                         SA-211D
```

Key elements:
- Field label + current value at the top
- History rows: value · CURRENT tag (if latest) · date · author · change reason (optional) · source document tag
- Source document tag (e.g. SA-208 R3, SA-211D) — links the change to a specific form or call

### Where it applies in the mockup

| Document | Fields with version history |
|---|---|
| SA-211D (Project Spec) | All filled fields — log shows when each was captured (IDQ, call 1, call 2, call 3) |
| Contact record | Stage, estimated value, interests, sentiment — log per call |
| Deal record | Stage, estimated value, blockers, next action |
| Ballpark worksheet | Line items — especially hand hewn (TBD → confirmed value when pricing sheet comes back) |
| IDQ | Fields that get overridden by later calls |

### Implementation in the mockup

**Data shape per field:**

```js
{
  label: 'Estimated total',
  current: '$285,000',
  history: [
    { value: '$285,000', date: 'Mar 10', author: 'Lukas Brenner', source: 'call3',    sourceLabel: 'Mar 10 call',  reason: null,              current: true  },
    { value: '$260,000', date: 'Feb 24', author: 'AI extraction', source: 'call2',    sourceLabel: 'Feb 24 call',  reason: 'ballpark estimate', current: false },
    { value: null,       date: 'Jan 22', author: 'AI extraction', source: 'call1',    sourceLabel: 'Jan 22 call',  reason: 'not yet captured',  current: false },
  ]
}
```

**UI behavior:**

- Field renders as normal (value, editable inline)
- A small `⊙` or clock icon appears on hover at the right edge of the field
- Clicking it expands the history log inline, same visual language as the form-section-box pattern
- History rows are read-only, newest first
- Source label is a link — clicking it opens the source call or form tab
- "CURRENT" badge in amber/green on the latest entry

**Version tracking on edits:**

When a user edits a field directly in the mockup, a new history entry is appended:
```js
{ value: newValue, date: 'now', author: 'Ana Olano', source: 'manual', sourceLabel: 'Manual edit', reason: null, current: true }
```

---

## Part 3 — Screenshot Viewer in the Call View

In the call view (past calls), add a **Screenshots** section after the transcript:

- Horizontal filmstrip of thumbnails (the saved `.jpg` files)
- Each thumbnail shows the timestamp label
- Click → expands to full size with the matching transcript segment alongside it
- If Claude flagged it as a form (`is_form: true`), show a small "form" badge on the thumbnail

For the mockup (no actual MP4 yet): seed call3 with 4-5 placeholder screenshot slots showing what this will look like once the pipeline runs on a real recording.

---

## Build Order

1. **Version history on SA-211D fields** (highest value, easiest to show the concept)
2. **Version history on contact + deal fields** (demonstrates the cross-call tracking)
3. **Screenshot filmstrip in call views** (placeholder thumbnails for now)
4. **Adapt extract_screenshots.py** for discovery calls (new prompt, GE file structure)
5. **Wire pipeline output → mockup** (after first real call runs through it)

---

## What This Enables for Dogfooding

After your first discovery call with a GE sales rep:

1. Run `extract_screenshots.py` on the recording
2. Screenshots + transcript segments drop into the call folder
3. AI extraction runs → CRM update written (existing pipeline)
4. Call view in mockup shows: summary, key moments, changelog, tasks, email draft, transcript, **screenshots filmstrip**
5. Every field that was updated shows the new value + full history of how it got there
6. Pre-call brief for the next call is auto-generated from accumulated history

The mockup becomes a real working tool for your own calls, not just a Thompson demo.
