# Manual Test: Expected Extraction Outputs

*Written by hand before running the extraction script. These are Ana's predictions of what Claude should propose after reading each transcript against the project files.*

*Hit rate target: 80%+ on high-confidence fields (explicit facts stated in the call).*

---

## Transcript 1: Golden Eagle Discovery Meeting — 2026-03-27

**Context:** First meeting. Ana + Daniel meeting Jay (owner), Tammy, Lucas Eichinger (sales), Andy Eichinger (pricing), Sean Flaherty (IT manager), Chris Stitcher (GM).

### Expected edits to `project-overview.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Stage | Prospect | Discovery | high |
| Champion | Unknown | Tammy | high |
| Next action | Schedule discovery call | Follow up on marketing + sales pain points; get Juan's context | medium |
| Pain Points | (none identified yet) | Paid search declining; SEO regressed after website rebuild two years ago; lead response lag (hours to 24 hrs); no analytics discipline; YouTube clicks down even with paid promotion | high |
| Marketing Situation | (none identified yet) | YouTube is primary lead source; $600k/year total marketing budget; JumpFly manages paid search (5,500 keywords) + SEO; Facebook boosted posts (+100k followers in last year); Instagram, TikTok active; Luke (Jay's son) does video content; search declining, AI search shift suspected | high |

### Expected edits to `people/jay-eichinger.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Priority interests | Unknown | AI rendering of floor plans (photorealistic walkthroughs); AI competitor analysis / SEO automation | high |
| Notes | (none yet) | Customers are top 10% earners; sales cycle 1–3 years; YouTube home tours are #1 lead source; frustrated that $600k marketing spend has waste he can't clean up | high |

### Expected edits to `people/tammy.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Title | Unknown | Internal operations (exact title unclear) | medium |
| Sentiment | Unknown | Positive — engaged, provided supplementary info on social media | medium |

### Expected edits to `people/sean-flaherty.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Title | Unknown | IT Manager | high |
| Notes | (none yet) | Manages JumpFly relationship for paid search; skeptical of analytics value; handles phone number tracking for ads; multi-hat role (IT + website + code) | high |

### Expected edits to `people/lucas-eichinger.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Title | Unknown | Sales staff | high |
| Relationship to Jay | Unknown | Stepson | high |

### Expected edits to `people/chris-stitcher.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Title | Unknown | General Manager | high |

### Expected edits to `people/andy-eichinger.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Title | Unknown | Pricing | high |
| Relationship to Jay | Unknown | Son (or family member — stated as "Andy Eichinger, he is lip pricing", unclear family relation) | low |

**Total expected high-confidence edits: ~12**
**Total expected medium/low: ~4**

---

## Transcript 2: Internal Planning (Ana + Daniel) — 2026-03-30

**Context:** Ana and Daniel planning the Golden Eagle engagement. Discusses diarized transcription pipeline, discovery plan, $15k proposal, Tammy's confirmed interest.

### Expected edits to `project-overview.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Value | TBD | $15,000 | high |
| Stage | Discovery | Active Engagement | medium |
| Next action | (previous) | Schedule 6 sales rep interviews + debrief with GE team on Friday; prep conversation guides | high |
| Notes | (none) | Golden Eagle uses Teams for meetings; Tammy confirmed wanting sales piece: recording meetings, transcripts, action items, follow-ups | high |

### Expected edits to `people/tammy.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Role in engagement | Unknown | Internal champion; confirmed interest in sales piece (meeting recordings, transcripts, action items, follow-up) | high |
| Confirmed interest | Unknown | Meeting recordings + transcripts + action items + follow-up automation | high |

**Total expected high-confidence edits: ~5**

---

## Transcript 3: CRM Mockup Demo to Dad (Ana + Juan) — 2026-03-30

**Context:** Ana showing the CRM mockup to her dad Juan (partly in Spanish). Mostly a product design discussion. Minimal Golden Eagle engagement updates.

### Expected edits to `project-overview.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Notes | (previous) | Add: audio capture options under consideration — Recall.ai (API for meeting bots), Teams native transcript, Whisper+pyannote on own servers | low |

**Note:** This transcript is mostly about the CRM product itself, not the Golden Eagle engagement. Expected edits are minimal. If Claude returns `[]` or near-empty for the GE project files, that is actually CORRECT behavior. The null-case test applies here.

**Total expected high-confidence edits: 0**
**Expected behavior: [] or 1 low-confidence edit**

---

## Transcript 4: Feature Planning (Ana + Daniel) — 2026-03-30

**Context:** Ana and Daniel discussing CRM feature scope. Golden Eagle specifics: email Chris to schedule rep interviews, scope concern about $15k, financing as a process area, floor plan back-and-forth as process area.

### Expected edits to `project-overview.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Next action | (previous) | Send email to Chris Stitcher (GM) to follow up on rep interview scheduling | high |
| Notes | (previous) | Scope warning: $15k may not be sufficient for full CRM rebuild; financing is a significant part of GE sales process (similar to car dealership); floor plan back-and-forth with architects is a long manual process quarterbacked by salespeople | medium |

### Expected edits to `people/chris-stitcher.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Role in engagement | Unknown | Manages the sales reps; contact for scheduling rep interviews | high |

**Total expected high-confidence edits: ~2**

---

## Transcript 5: Coordination (Ana + Daniel) — 2026-03-31

**Context:** Ana and Daniel checking in on discovery interview status. Reps not responding. Priority order established. Training curriculum discussed.

### Expected edits to `project-overview.md`

| Field | From | To | Confidence |
|-------|------|----|------------|
| Interview Status | (none scheduled) | Emails sent to Tammy and Sean; reps not responding within 24 hours; escalation to Chris being considered | high |
| Next action | (previous) | Escalate to Chris if no response by midday; schedule Tammy ASAP for candid org download; Jay last (after reps) | high |
| Notes | (previous) | Interview priority order: Tammy first → Sean → Chris (after talking to reps) → Jay last; training curriculum (AI 101) being prepared for next week; focus on one end-to-end demo feature rather than multiple; coordinate with Juan to avoid building duplicate systems | medium |

**Total expected high-confidence edits: ~2-3**

---

## Summary Table

| Transcript | Expected high-conf edits | Expected behavior |
|-----------|--------------------------|-------------------|
| T1 — Discovery | ~12 | Heavy update across all people files + project-overview |
| T2 — Internal planning | ~5 | Value, stage, next actions, Tammy confirmed |
| T3 — Mockup demo | 0 | Near-empty or `[]` — this is correct |
| T4 — Feature planning | ~2 | Email to Chris, scope warning |
| T5 — Coordination | ~2-3 | Interview status, priority order |

---

## What to look for in the actual outputs

**Green flags (Claude doing well):**
- `old_value` is verbatim text from the file
- `file_path` matches a real file in `test-data/golden-eagle/`
- `source_quote` actually appears in the transcript
- T3 returns `[]` or near-empty

**Red flags (hallucination / errors):**
- `old_value` not found in the file (SEARCH/REPLACE would silently fail)
- `file_path` references a file that doesn't exist
- Edits proposed for T3 that aren't actually in the transcript
- Proposes structural changes (new headings, new fields) that don't exist in the files
