# Research: Real-Time Call Notetaking UX Patterns
*April 2026*

---

## Tool-by-Tool Analysis

### 1. Granola — The Most Relevant Benchmark

**Core concept**: Blank scratchpad during the call. When the meeting ends, Granola combines your scratchpad with its transcript and produces polished, structured notes. Human notes act as an emphasis signal to the AI.

**During-meeting UX:**
- Blank note editor. Type anything — rough fragments, keywords, abbreviations. No pressure to be clean.
- Markdown headers optionally pre-structure sections (`# Action Items`). If you add them, the AI respects them.
- Paste images directly into the scratchpad during the call.
- Live transcript accessible but deliberately not the primary focus — small animated circle tab at the bottom (a discoverability complaint).
- No bot joins the call. Captures Mac system audio. Other participants don't know it's running.

**After-meeting UX:**
- ~30 seconds after the call ends, enhanced notes appear.
- Your scratchpad text in **black**. AI-synthesized additions in **gray**.
- Every AI-added bullet is hyperlinked — click it, jump to exact timestamp in transcript.
- One unified document, not two separate views.
- Share via link or email. HubSpot integration auto-pushes summaries.

**What users love:** Scratchpad model removes note-taking anxiety. No bot. Gray/black distinction. Timestamp links. ~30 second turnaround.

**What users complain about:** Live transcript pane hard to find. No onboarding. Mac-only origin. If you forget to open it at the start, no backfill.

---

### 2. Otter.ai — The Incumbent with Privacy Problems

**During-meeting UX:**
- Bot joins the call as a named participant. Auto-joins via calendar.
- Live transcription scrolling in real time.
- During recording: add highlights, comments, images, interact with "Otter Chat."
- "Takeaways panel": manually highlight moments as Decisions or Action Items — trains the AI on what matters.

**Post-call:** Full searchable transcript. Click any word → audio plays from that moment (flagship differentiator). Salesforce, HubSpot, Notion, Slack integrations.

**What users love:** Transcript-to-audio playback (cited as "magic"). High transcription accuracy.

**What users hate (severe):** Bot joins confidential meetings, records without consent, emails transcripts to all attendees. Federal class-action lawsuit filed August 2025 alleging recording private conversations without consent. 84% of users change how they speak knowing an AI notetaker is present.

---

### 3. Fireflies.ai — Most Feature-Dense During-Call Experience

**Live Assist (during-call sidebar):**
- Right-side panel appears within 10 seconds of meeting start.
- Sections: AI Notes (real-time outline), Live Transcript, Action Items, AskFred (Q&A), Sales Assist.
- **Bookmarks**: one click tags a moment as Positive, Action Item, Important, or Concern. Timestamped.
- **Voice commands**: "Hey Fireflies, bookmark this as the new pricing agreement." Voice-triggered capture without typing.

**Desktop App:** Movable overlay delivering Live Assist without leaving the meeting window.

**What users love:** One-click bookmark. Voice commands for task creation. Real-time notes feel like "having an assistant in the room."

**What users complain about:** Feature overload. Bot joins visibly. Expensive. Real-Time Notes initially limited to Google Meet.

---

### 4. Fellow.app — Pre/Post-Meeting Workflow Champion

**During-meeting UX:**
- Zoom App: embeds Fellow notes in a side panel within Zoom.
- `/` command opens content insertion menu — add talking points, action items, section headings, embeds.
- `Tab`/`Shift+Tab` for indenting. `{{user}}` and `{{meeting}}` macros auto-populate names.
- Item-type dropdown converts a bullet into an action item, section header, etc.

**Post-call:** AI summary and action items. Action items assigned to specific people with due dates, syncs to Asana/Jira/Linear. "Note series" for recurring meetings — continuous record of all prior sessions.

**What users love:** Pre-call agenda-building. Collaborative real-time editing. Action item ownership with due dates. Note series for recurring meetings.

**What users complain about:** Overkill for ad hoc field calls. Setup friction. AI summarization is post-meeting, not live.

---

### 5. Notion — Powerful but Structurally Wrong for Live Capture

The live-capture problem: initiating a meeting note is clunky — navigate to database, create entry, add properties. No global hotkey. Load times unacceptable mid-call.

Power user workaround: permanently-open "Daily Scratchpad" page.

---

### 6. Apple Notes — Friction-Free but Featureless

**Quick capture strengths:**
- macOS `Cmd+Shift+Y` summons Quick Note — a floating note from anywhere, even in full-screen apps. Opens in under 1 second.
- Lock Screen widget for tap-to-create on iOS.

**What Apple Notes teaches us:** Zero friction to open is the baseline. `Cmd+Shift+Y` from any application is the standard. Under 100ms, no navigation cost.

**What doesn't work:** Notes don't go anywhere after the call. No CRM connection, no action item extraction.

---

### 7. Bear — Keyboard-First Inline Tagging

- Markdown rendered in real time — `# Heading` becomes bold text as you type.
- Inline tagging: type `#tag` — no separate tagging UI, no mode switch.
- Internal note linking with `[[note title]]`.

**What Bear teaches us:** Inline tagging is zero-friction categorization that doesn't interrupt writing flow. Real-time Markdown creates structure without toolbar interaction.

---

### 8. Superhuman — Speed Benchmark

Key principles applicable to live notetaking:
- **100ms rule**: Interactions under 100ms feel instant.
- **Single-key actions**: Most common actions cost 1 keystroke, no confirmation, no menu.
- **Natural language input**: `3d`, `next tuesday 9am` — no calendar picker.

Applied to notetaking: flagging as important / action item / follow-up should cost 1 keystroke or 1 tap. Never require menu navigation during a live call.

---

### 9. Jamie — The Compact Draggable Overlay

- Floating recorder widget — compact, draggable, always-on-top.
- Bot-free: transcribes computer audio directly.
- **Private scratchpad**: notes that stay completely separate from the shared summary. Personal flags, rough reactions, private thoughts don't pollute the CRM-facing record.

**Key UX insight:** The private scratchpad / shared summary split is important. Not everything a rep writes during a call should flow into the CRM output.

---

## Cross-Cutting Patterns

### Q1: How do tools handle fast tagging mid-call?

Four approaches:

**A. One-click bookmarks (Fireflies):** One click tags a moment as Positive / Action Item / Important / Concern. Zero typing. Fixed category set.

**B. Voice commands (Fireflies):** Powerful in theory, awkward in practice — remembering syntax while listening to a client is hard.

**C. Inline text markers (Granola, Bear, Jamie):** User types `ACTION:`, `DECISION:`, `#follow-up` inline. AI reads markers post-call. Zero UI friction, relies on user discipline.

**D. Auto-detection (Otter, Fireflies):** AI detects phrases like "can you send that" and auto-creates action items. Unreliable — false positives common.

**Key finding:** No tool has cracked truly frictionless mid-call tagging. Best approaches: (1) one-tap buttons with fixed categories, or (2) inline text markers the AI reads after the fact.

---

### Q2: Floating panels, sidebars, or full-screen?

- **Sidebar embedded in meeting tool (Fellow in Zoom):** Stays in context, collaborative. Takes screen real estate from video grid — severe on small laptops.
- **Separate floating window (Jamie, Granola):** Draggable, anywhere, doesn't affect meeting layout. User manages positioning.
- **Full-screen:** Works with second screen; on one screen requires switching away from the call.

**Key finding for Sundial:** Compact floating overlay + full-screen experience on second screen or between calls.

---

### Q3: Scratchpad vs. structured

**Granola's answer (most elegant):**
- During: totally freeform scratchpad. No structure required.
- After: AI applies template structure to scratchpad + transcript combined.
- Human notes act as emphasis signals.

**Key finding:** The structured vs. free text tension is a **timing** problem, not a format problem. Free text *during* the call, structure *after* the call, is the winning pattern.

---

### Q4: Post-call — connecting notes to transcript

- **Click-to-timestamp (Otter, Granola, Fireflies, Fathom):** Every sentence in transcript is a link. Click it, audio plays from that point.
- **Search-to-playback (Otter):** Type query → results → click → hear that moment.
- **Topic segmentation (Fireflies, Read.ai):** AI segments transcript into named topics.
- **Action item tracking with owners + due dates (Fellow, Fireflies):** Extracted items assigned to people with due dates, syncing to task managers.

**Key finding:** Most trusted post-call workflow: structured summary → click any bullet → hear the audio. Users spot-check AI output in seconds.

---

### Q5: Clever UX patterns for minimizing friction

1. **No-bot audio capture** — the single biggest friction reducer.
2. **Scratchpad as emphasis layer** — users only note what matters. Cognitively liberating.
3. **Auto-start on calendar events** — zero user action required.
4. **Floating always-on-top widget** — capture surface visible at all times.
5. **Inline tagging with `#` syntax** — one gesture, no toolbar, no mode change.
6. **Single-key hot actions** — `A` = action item. `D` = decision. `F` = follow-up.
7. **Template sections as cognitive prompts** — headers like `# What did we agree to?` keep notetaker on track.
8. **Voice dictation** — hold hotkey, speak, text appears. 3x faster than typing.
9. **Auto-populate from CRM before the call** — context ready before first word spoken.

---

### Q6: What users love and hate

**Universally loved:**
- No bot joining the call.
- Click-any-word → hear-the-audio. Cited as "magic" across Otter, Fireflies, Fathom, tl;dv.
- Notes ready within seconds after call ends.
- AI that clearly distinguishes what it generated vs. what the human wrote.
- Templates matched to the specific meeting type.

**Universally hated:**
- Bots that join without explicit per-meeting consent.
- Auto-sharing transcripts with people who didn't opt in.
- Slow load times / startup friction when call has already started.
- AI action items with false positives or missing the real ones.
- Single-screen layout conflicts.
- Overwhelming post-call output — too many words, not enough signal.

---

## Synthesis / Implications for Sundial Design

### Core insight

Tools users love most solved the **timing problem**: free capture during the call, AI-structured output after the call. Tools that frustrate users imposed structure during the call or failed on privacy/consent.

### 14 concrete implications

**1. No bot joins the call — surface this as a feature.** Otter's lawsuits are disqualifying for relationship-sales. Say it explicitly: "Sundial never joins your call as a visible participant."

**2. Compact floating overlay, not a sidebar.** Field reps on laptops with one screen. Floating, draggable, always-on-top. Small by default (~50-80px tall collapsed), expands on demand.

**3. Scratchpad is the primary capture surface.** Blank text area, no required structure, typos welcome. AI reads it post-call as emphasis signal. Do not force structure during the call.

**4. One-keystroke actions for three most common mid-call note types:**
- `A` (or button) → action item for me to do
- `C` (or button) → client commitment / promise they made
- `F` (or button) → follow-up reminder

Three buttons, always visible. No menu navigation required.

**5. Every AI-generated bullet links back to transcript timestamp.** Granola's gray/black distinction + timestamp hyperlinks. Tap any AI summary line → hear the original quote. Highest-trust post-call feature.

**6. "Find me where we said X" → audio playback search.** Text search in transcript → click result → play audio from that moment. Cited as "magic" everywhere that offers it.

**7. Templates configured once per meeting type, not per call.** Common Sundial templates:
- Discovery call (pain points, decision makers, timeline, budget, next steps)
- Progress check-in (what's done, blocked, next milestone, client mood)
- Closing call (final objections, agreed terms, next steps, signature timeline)
- Follow-up call (outstanding items, commitments review, new questions)

**8. "30 seconds after the call" transition is a critical UX moment.** Target: enhanced notes visible before the rep puts the phone down. Context is hottest and corrections are easiest in this window.

**9. Image paste into live scratchpad.** For a construction/land context: photos of a lot, sketched site plan, documents. `Cmd+V` image paste. Show thumbnail inline. Include in post-call notes.

**10. Separate private scratchpad from CRM-facing output.** Notes like "client seems anxious, may be losing interest" should not appear in the CRM record. Let reps mark lines as private before the summary is generated.

**11. Voice dictation for notes.** Hold hotkey, speak, text appears at cursor. 3x faster than typing. Works for scratchpad and quick action fields.

**12. CRM-primed pre-call brief.** When the rep opens the copilot, show: last call date, last extracted action items, current project stage, open commitments. Sundial's briefing feature already does this — wire it to the copilot open state.

**13. Avoid Otter anti-patterns by design:** Never auto-share transcripts. Never join a call without deliberate per-call consent. Never auto-email attendees.

**14. Post-call action items must be assigned and dated, not just listed.** Action items have an owner (rep or client) and a due date. Auto-suggest date from transcript ("let's talk again next week" → suggest 7 days out). One-tap confirm or adjust.

---

### The single most important feature to build first

**Click any bullet in the AI summary → hear the audio from that moment.**

Cited as "magic" across Otter, Fireflies, Fathom, and tl;dv. Highest-trust post-call feature. Converts skepticism into confidence. Build it before any other post-call enhancement.

---

*Sources: Granola product docs, Granola TechCrunch launch, tl;dv Granola review 2026, Otter.ai help docs, NPR/HackerNews/Workplace Privacy Report on Otter class-action lawsuit August 2025, Fireflies Live Assist docs, Fellow help center, Colibri.ai product pages, Read.ai help docs, Jamie.ai product pages and reviews, Bear.app keyboard shortcut docs, Fathom vs tl;dv reviews, Superhuman design philosophy (Rahul Vohra), Nielsen Norman Group group notetaking, DigitalOcean AI notetaker roundup.*
