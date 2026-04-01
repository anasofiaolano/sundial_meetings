# Phase 1: AI Extraction

Validates the core AI loop in isolation. Given a set of free-form markdown project files and a call transcript, call Claude and get back a JSON array of proposed edits. No database, no server, no git — just: transcript + files in, edits out.

**Status:** Complete and working. All 5 Golden Eagle transcripts extract cleanly with zero validation failures.

---

## What was built

| File | Purpose |
|------|---------|
| `scripts/phase-1/run-all.js` | Runs all 5 transcripts through Claude, saves results to `test-data/results.json` |
| `scripts/phase-1/report.js` | Reads results + expected outputs, generates `test-data/report.html` |
| `scripts/phase-1/test-extraction.js` | Single-transcript runner (for debugging one at a time) |
| `test-data/golden-eagle/` | Project files for the Golden Eagle engagement (free-form markdown) |
| `test-data/transcripts/` | 5 real transcripts (Mar 27, 30, 30, 30, 31) |
| `test-data/expected-outputs.json` | Manual predictions — what Claude should propose per transcript |
| `test-data/results.json` | Saved extraction runs (appends, never overwrites — compare across prompt iterations) |
| `test-data/report.html` | Visual test report — open in any browser |

---

## How to run

```bash
# Run all 5 transcripts through Claude (saves to results.json)
node scripts/phase-1/run-all.js

# Generate the visual report
node scripts/phase-1/report.js
open test-data/report.html

# Run a single transcript (for debugging)
node scripts/phase-1/test-extraction.js test-data/transcripts/transcript-01-golden-eagle-discovery.txt
```

---

## How the edit schema works

Every proposed edit is a find-and-replace:

```json
{
  "file_path": "people/jay-eichinger.md",
  "field_label": "Jay Eichinger notes",
  "old_value": "(no notes yet)",
  "new_value": "Owner of Golden Eagle Log Homes. Top priority: photorealistic AI rendering...",
  "confidence": "high",
  "source_quote": "my biggest dream would be... renderings that look photorealistic"
}
```

- `old_value` — exact text currently in the file (verbatim). Find this, replace it.
- `new_value` — the replacement. Can be a full rewrite, an augmentation, or a new section appended.
- `source_quote` — the sentence from the transcript that justifies the change. Audit trail.
- `field_label` — human-readable topic label for the report. Not a database field.

**The gating rule:** Claude has been given the full file contents in context. `old_value` must come verbatim from those contents. If validation fails (old_value not found in file), the edit is flagged — SEARCH/REPLACE would silently fail.

---

## How the test report works

Running `report.js` compares Claude's actual output against the manual predictions in `expected-outputs.json`:

- **✅ Hits** — predicted and captured. Shows the actual edit Claude proposed.
- **❌ Missed** — predicted but not found in Claude's output. Shows what was expected and why.
- **⚠️ Not expected** — Claude proposed it but it wasn't in the predictions. Could be a good find or a hallucination — review manually.

**Matching logic:** an expected edit is satisfied if any actual edit for the same file has a `new_value` containing the expected substring. One Claude edit (which often bundles multiple facts per file) can satisfy multiple expected edits.

**Validation:** every edit is independently checked — does `old_value` exist verbatim in the file? Failures mean the SEARCH/REPLACE apply step would break downstream.

---

## Key findings from run #3

- Free-form markdown files work better than structured fields. Claude naturally writes prose, adds sections, and bundles related facts — which is more useful than one edit per field.
- T3 (mockup demo to dad) produced 2 edits despite being an internal product call — worth monitoring. The prompt rule "if no new client facts, return []" partially works but isn't perfect.
- Zero validation failures across all 5 transcripts on run #3.
- Token counts well within budget (4,329–11,867 tokens per transcript, limit 160,000).

---

## Prompt version: extraction-v1

See `scripts/phase-1/run-all.js` for the full system prompt. Key rules:
1. Only propose edits for facts explicitly stated in the call
2. `old_value` must be copied verbatim from the file content provided
3. Augmenting = include existing content in `old_value`, extend it in `new_value`
4. If no new client facts in the transcript, return `[]`
