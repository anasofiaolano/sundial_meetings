# State

<!--
  INSTRUCTIONS FOR THE AGENT:

  This is your hot context — the note pinned to the amnesiac's chest.
  Read this FIRST after compaction or session start.

  RULES:
  - ALWAYS overwrite after every meaningful action (the ONE exception to "never overwrite")
  - Max 30 lines — if it's longer, you're putting too much detail
  - If STATE.md and DECISION-LOG.md conflict, STATE.md wins (it's more recent)
  - This is the recovery mechanism — if you don't update it, recovery breaks

  RECOVERY PROTOCOL (3 steps — ALL mandatory):
  1. Read this file (STATE.md) — know WHERE you are (~5 seconds)
  2. Read last 20 entries of DECISION-LOG.md — understand recent decisions and WHY (~30 seconds)
  3. Read the files listed in "Files to read next" below — get WHAT you're working on

  All three steps are mandatory. Steps 1-2 tell you where you are. Step 3 tells you what you're working on.

  SESSION-START VALIDATION (run before beginning work):
  - [ ] This file exists and has content (not just the template)
  - [ ] "Last updated" is from a recent session (not days stale with no explanation)
  - [ ] Phase makes sense (not stuck in a completed phase)
  - [ ] If Build phase: active workstream file exists and has progress
  - [ ] If Epochs phase: latest epoch file exists
  - [ ] DECISION-LOG.md last entry is consistent with this file

  If anything fails: flag to the human. Don't silently continue with inconsistent state.

  If this file is still a template (no project name filled in), this is a brand new project.
  Start at Phase 1: Epochs.
-->

**Project:** Sundial Meetings CRM
**Phase:** Epochs — Between-Epoch Evaluation
**Epoch:** 1 complete; evaluation written, pending human + agent critique
**Preset:** Full
**Mode:** Solo
**Active workstream:** none
**Blockers:** none
**Last updated:** 2026-03-31T14:00
**Last action:** Wrote eval-2-piecemeal.md — full web research + staff engineer critique + openclaw prior art. 8 corrections to eval-1. Piecemeal validation plan: 8 test scripts in order. Key changes: git commit per CALL not per edit; output_config.format for structured output; 409 conflict detection mandatory; prompt_version tracking; Claude timeout + retry; index lock self-healing; old_value staleness check.
**Next action:** Human reviews eval-2. Then: seed test data + build Piece 1 (AI extraction script) — highest priority validation.
**Files to read next:** epochs/01-EPOCHS/eval-2-piecemeal.md, epochs/01-EPOCHS/eval-1-best-practices.md
