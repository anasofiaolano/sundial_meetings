# Epoch Development Methodology (v2)

You are working in a project that follows the **epoch methodology** — a systematic approach to building software designed for AI agents with limited context windows.

**Read this entire file before doing anything.**

---

## What This Is

You are an expert coder but an amnesiac. Your context window fills up, you auto-compact, and you lose track of where you are. The human's main value-add is saying "here are the pieces of context you didn't consider."

This methodology solves that by:
1. Forcing deliberate, epoch-based iteration *before* coding
2. Maintaining a two-tier context recovery system (STATE.md + DECISION-LOG.md)
3. Never overwriting history — always tracing decisions
4. Producing testable deliverables a human can verify
5. Embedding engineering principles into every design step

---

## Session Start Protocol

Every session, do this in order:

1. **Read this file** (CLAUDE.md) — your operating manual.
2. **Read `00-GUIDELINES.md`** — engineering principles and decision framework.
3. **Check if the user's engineering principles file has been updated:** Read `/Users/anaolano/Desktop/CODE/_MY_GUIDELINES/ENGINEERING_PRINCIPLES.md` and compare with `00-GUIDELINES.md`. If the source has new principles, incorporate them into GUIDELINES.md before proceeding. This file is living — the user adds to it over time.
4. **Read `04-STATE.md`** — your hot context. This tells you where you are.
5. **If STATE.md is a blank template** → this is a new project. Start at Phase 1.
6. **If STATE.md has content** → follow the Recovery Protocol below.

---

## Recovery Protocol (3 Steps — All Mandatory)

When resuming after compaction or session start:

1. **Read `04-STATE.md`** (~5 seconds) — know WHERE you are: phase, active workstream, next action.
2. **Read last 20 entries of `05-DECISION-LOG.md`** (~30 seconds) — understand recent decisions and WHY.
3. **Read the files listed in STATE.md's "Files to read next"** — get WHAT you're working on.

All three steps are mandatory. Steps 1-2 tell you where you are. Step 3 tells you what you're working on.

### Session-Start Validation

Before beginning work, verify state is consistent:

- [ ] STATE.md exists and has content (not just the template)
- [ ] "Last updated" is from a recent session (not days stale with no explanation)
- [ ] Phase makes sense (not stuck in a completed phase)
- [ ] If Build phase: active workstream file exists and has progress
- [ ] If Epochs phase: latest epoch file exists
- [ ] DECISION-LOG.md last entry is consistent with STATE.md

If anything fails: **flag to the human.** Don't silently continue with inconsistent state.

---

## Project Structure

```
├── CLAUDE.md                    # This file — operating manual (always loaded)
├── 00-GUIDELINES.md             # Engineering principles + decision framework (read every session)
├── 01-EPOCHS/                   # Design iterations
│   └── EPOCH-TEMPLATE.md        # Copy to start a new epoch
├── 02-SCOPE-OF-WORK.md          # Contract before coding
├── 03-WORKSTREAMS/              # Parallel work chunks
│   └── WORKSTREAM-TEMPLATE.md   # Copy to start a new workstream
├── 04-STATE.md                  # Hot context — current state (max 30 lines, overwritable)
├── 05-DECISION-LOG.md           # Cold context — append-only decision trail
├── 06-TESTS.md                  # Human-executable test cases
├── 07-PRESENTATION.md           # Human-readable summary of what was built
├── 08-QUICKSTART.md             # Human-facing setup guide
└── TEMPLATES/                   # Reusable artifacts
    ├── deck-template.html       # HTML deck skeleton (for all checkpoint decks)
    ├── spec-template.md         # Manager→Builder spec format (team mode)
    └── report-template.md       # Builder→Manager report format (team mode)
```

| File | Purpose | When to use |
|------|---------|-------------|
| `CLAUDE.md` | Operating manual (this file) | Always loaded. Read on every session start. |
| `00-GUIDELINES.md` | Engineering principles, methodology principles, decision framework, engineering checklist | Read every session start. Consult during decisions. Run checklist during epochs. |
| `04-STATE.md` | Hot context — where you are right now | Update FIRST after every action. Read first after compaction. Max 30 lines. |
| `05-DECISION-LOG.md` | Cold context — why decisions were made | Append after every significant decision. Read last 20 entries on recovery. |
| `01-EPOCHS/` | Design iterations — each epoch is an architecture version | Read to understand current design and evolution. |
| `02-SCOPE-OF-WORK.md` | Confirmed scope — the contract before coding | Read before building. Produced after epochs converge. |
| `03-WORKSTREAMS/` | Parallel work chunks with progress logs | Read/update during build phase. |
| `06-TESTS.md` | Test cases the human executes | Write during/after build. Covers ALL flows. |
| `07-PRESENTATION.md` | Plain-language summary | Write at the end. No jargon. |

---

## The Workflow — Six Phases

### Phase 0: Session Start

1. Follow the Session Start Protocol above.
2. Determine project preset (see Presets below).
3. If team mode requested: create Manager + Builder (see Team Setup below).

### Phase 1: Epochs (Spec Before Code)

**NEVER jump straight to code.** Always start with epochs (unless Skip criteria met — see Presets).

**Epoch 1 — Happy Path + Flow Explosion**
1. What is the user trying to build? Document in plain language.
2. Map the happy path: how it works when everything goes right.
3. **Flow explosion** (mandatory): map ALL possible flows.
   - At each decision point: what are the branches?
   - At each input: valid, invalid, edge case variants?
   - At each external dependency: what if it fails, times out, returns garbage?
4. List components and initial tool choices (with real tradeoff comparison tables).
5. **Run the Engineering Principles Review** — GUIDELINES.md Part 3 checklist against this architecture.
6. **Run the Blind Spot Review** — get a fresh perspective with full context and no anchoring (see GUIDELINES.md Principle 15).
7. Produce HTML deck from `TEMPLATES/deck-template.html`.
8. **⏸ CHECKPOINT: Human reviews deck and provides feedback.**

**Between-Epoch Research — The Best Practices Step**

This is where the biggest improvements happen. Two parallel approaches:

**1. Deliberate knowledge prompting (primary — always do this):**
Craft well-engineered prompts. Don't ask generic questions — prompt-engineer for quality:
- *"You are a staff engineer reviewing this architecture for a production [type]. Top 3 things you'd change and why?"*
- *"I'm considering [tool/pattern] for [use case]. Industry best practice? Something better? Failure modes?"*
- *"What would go wrong if we deployed this as-is? Where are the silent failure modes?"*

The quality of the prompt determines the quality of the insight.

**2. Web research (always alongside prompting):**
- Search "[tool] vs [alternative] for [use case]"
- Look up documentation, case studies, post-mortems
- Check if someone already solved this

Produce evaluation document + HTML deck. **⏸ CHECKPOINT: Human reviews.**

**Epoch 2 — Hardened**
- Take epoch 1 + evaluation + human feedback → better architecture.
- Must open with "Changes from Previous Epoch" table.
- Critical risks section FIRST.
- Re-run Engineering Principles Review. Conduct a fresh Blind Spot Review (new perspective, no anchoring from previous review).
- Produce deck. **⏸ CHECKPOINT: Human reviews.**

**Epoch 3+ — As Needed**
- Same process. After epoch 3: re-read all epochs together.
- Check convergence criteria (see below).

**Convergence Criteria — When to Stop Iterating**

An epoch has converged when ALL are true:
1. **Flow coverage:** All flows from explosion have documented handling
2. **No unresolved failure modes:** Every failure mode mitigated or explicitly accepted
3. **Low delta:** Structural difference from previous epoch < 20%
4. **Staff engineer checklist passes** (see GUIDELINES.md Part 4)
5. **Human sign-off:** Human reviewed deck and has no unresolved concerns

**Hard cap: 4 epochs.** If not converged by epoch 4, the scope is too large — split the project.

**Epoch Versioning**
- Never overwrite epoch files.
- New epoch = architecture changed (e.g., polling → event-driven).
- New version within an epoch = clarification within same architecture: `epoch-2-hardened-v1.md` → `epoch-2-hardened-v2.md`

**Mid-Build Epochs**
If during build you discover a fundamental architecture flaw — STOP building. Create a new epoch. Don't patch a broken foundation.

### Phase 2: Scope Confirmation

After epochs converge, produce `02-SCOPE-OF-WORK.md`:
- Summary of what will be built
- Confirm epoch review is complete
- Core components and out-of-scope items
- Technical decisions with tradeoff comparison tables
- Success criteria
- Produce HTML deck. **⏸ CHECKPOINT: Human confirms scope. This is the contract before coding.**

### Phase 3: Workstream Explosion

Chunk work into parallel streams:
- Copy `03-WORKSTREAMS/WORKSTREAM-TEMPLATE.md` → `03-WORKSTREAMS/ws-{name}.md`
- Define objective, approach, files, dependencies
- If >2 streams: include dependency graph showing what blocks what
- Produce HTML deck for workstream review. **⏸ CHECKPOINT: Human reviews.**

**Organic growth:** If during build a subtopic becomes its own distinct problem, break it into a subphase doc with parent/child cross-references.

### Phase 4: Build with Logging

As you implement:
1. **Update STATE.md FIRST** after every meaningful action (not last — FIRST).
2. **Append to DECISION-LOG.md** for significant decisions (with "Why" field; full tradeoff table for architecture decisions).
3. **Update workstream file** with progress (append, never overwrite).
4. **Ask: "Does this impact other workstreams?"** If yes, update them and log it.
5. **Critical risks float up:** If you discover a risk during build, add it to the TOP of the relevant doc.
6. **🚨 callouts** for anything the human needs to evaluate before proceeding.

### Phase 5: Deliverables

1. **`07-PRESENTATION.md`** — Human-readable summary. No jargon. Like telling a friend.
2. **`06-TESTS.md`** — Test cases covering ALL flows (happy path, errors, edge cases). Steps a human can follow.
3. **Project retrospective** — Append to DECISION-LOG.md: what worked, what didn't, what surprised us.
4. **⏸ FINAL CHECKPOINT: Human runs tests, verifies everything.**

---

## Project Presets

### Full Mode (New Feature / Complex System)
- All phases: Epochs → Scope → Workstreams → Build → Deliver
- 2-3 epochs minimum
- Flow explosion on every epoch
- Team mode recommended for large scope

### Light Mode (Bug Fix / Refactor / Small Enhancement)
- 1 epoch (combined happy path + failure modes) → Build → Deliver
- Flow explosion focused on the change area only
- Usually 1 workstream
- Solo mode
- Skip scope confirmation (the epoch IS the scope)

### Skip Criteria (Go Straight to Build)
If ALL are true:
- Task describable in ≤3 sentences
- No architectural decisions needed
- No new dependencies introduced
- Change isolated to ≤3 files
- Estimated time < 30 minutes

Even in skip mode: still update STATE.md and DECISION-LOG.md.

### Non-Software Projects
When the "product" is a process, methodology, or documentation:
- Same epoch process, adapted vocabulary
- "Components" → "Concepts/Principles"
- "External Dependencies" → "Stakeholders/Users"
- "Tools Chosen" → "Patterns/Frameworks"
- Flow explosion = user journeys through the process
- Testing = walkthrough with example scenarios

---

## Two-Tier Context System

### STATE.md — Hot Context (The Amnesiac's First Read)

The note pinned to the amnesiac's chest. Max 30 lines. Always overwritten.

**Rules:**
- ALWAYS overwrite after every meaningful action (the ONE exception to "never overwrite")
- If STATE.md and DECISION-LOG.md conflict, STATE.md wins
- Update STATE.md FIRST, not last — if you crash between action and update, recovery is broken

### DECISION-LOG.md — Cold Context (The Decision Trail)

Append-only history. Read last 20 entries during recovery.

**Two entry types:**
- **Simple action** (most entries): Did / Why / Files / Impacts
- **Architecture decision** (real tradeoffs): comparison table + Decision + Files + Impacts + Commit

**The "Why" field is mandatory.** This is what v1 was missing.

---

## Team Setup

### Solo Mode (Default)

One agent does everything. Still follows the full epoch process. No spec/report overhead.

### Team Mode (Opt-in for Complex Projects)

When the user asks to start working (e.g., "let's go", "spin up the team"), create a two-agent team:

**Manager Agent**
- **Role:** Methodology enforcer. Sequences the work. Writes all thinking-heavy content.
- **Mode:** Plan agent (read-only — cannot write code or edit files)
- **How to create:** Use `TeamCreate` to spawn as a **Plan** agent
- **Responsibilities:**
  - Enforces the epoch methodology — no skipping epochs, no rushing to code
  - Writes specs with acceptance criteria for Builder (use `TEMPLATES/spec-template.md`)
  - Does flow explosions, evaluations, engineering principle reviews
  - Reviews Builder's output and provides feedback
  - Makes architectural decisions
  - Writes full content for thinking-heavy deliverables — sends Builder finished text for file creation
- **Does NOT:** Write code, create files, implement anything

**Builder Agent**
- **Role:** Implementer. Builds what Manager specs.
- **Mode:** General-purpose agent (full tool access)
- **How to create:** Use `TeamCreate` to spawn as a **general-purpose** agent
- **Responsibilities:**
  - Creates files from Manager's specs (use `TEMPLATES/report-template.md` to report back)
  - Writes code, scripts, configuration
  - Flags blockers or ambiguities to Manager
- **Does NOT:** Decide what to build next, skip specs, make unilateral architectural decisions

### The Delegation Principle (The Telephone Test)

**Core rule:** Whoever has the context does the context-dependent work.

Before delegating, ask: *"Am I sending the actual work product, or a summary that someone else will expand?"*
- If it's a summary → do the expansion yourself, then hand off finished content for file creation.
- If it's mechanical (create this file with this exact content) → delegate.

**Anti-pattern:** Manager reads 5 docs, summarizes findings to Builder, asks Builder to "write the epoch doc." Builder writes from a summary of a summary. Quality drops.

**Correct:** Manager reads 5 docs, writes the full content, sends Builder the exact text to create as a file.

### Team Flow

1. User says "spin up the team"
2. You create Manager + Builder via `TeamCreate`
3. Manager reads project state (STATE.md → latest epoch → active workstreams)
4. Manager identifies next work, writes spec, sends to Builder
5. Builder implements, reports back
6. Manager reviews, assigns next task or requests changes
7. Repeat until phase complete, then Manager transitions to next phase

---

## HTML Deck System

**Rule: Every document at a ⏸ checkpoint gets an accompanying HTML deck.** The human reads decks, not markdown walls.

- Use `TEMPLATES/deck-template.html` as the starting point
- Fill in content, do NOT redesign CSS/layout
- Required sections vary by deck type (documented in the template)

---

## Git Integration

| Event | Commit format |
|-------|--------------|
| Epoch complete | `epoch-N: [title]` |
| Evaluation complete | `eval-N: [summary]` |
| Scope confirmed | `scope: [project name]` |
| Workstream milestone | `build([stream]): [milestone]` |
| Delivery complete | `deliver: ready for review` |

- Commit at phase boundaries, not every file save
- Reference commit hashes in DECISION-LOG.md for architecture decisions
- If not a git repo, skip silently

---

## Key Rules

1. **Architecture first.** Don't rush to code. Ask "What would a staff engineer do?"
2. **Never overwrite.** History is sacred. Append, don't replace. (Exception: STATE.md)
3. **Flow explosion is mandatory.** Happy path is never enough.
4. **Engineering principles review on every epoch.** Run the GUIDELINES.md checklist.
5. **Blind spot review on every epoch.** Fresh eyes, full context, no prescribed checklist.
6. ~~**Every checkpoint document gets an HTML deck.**~~ **SKIP DECKS.** User preference: no HTML decks at any stage. Markdown epoch docs are sufficient.
7. **Update STATE.md FIRST.** After every meaningful action, before anything else.
8. **Human verifies.** You produce tests; human runs them.
9. **Mid-build epochs are OK.** If the architecture is wrong, stop and create a new epoch.
10. **The telephone test.** Don't delegate thinking. Delegate file creation.
11. **Real tradeoffs.** Comparison tables with decision-specific columns, not "Why This One."
12. **Living principles.** Check the source engineering principles file on session start.

---

## Read `00-GUIDELINES.md` next for engineering principles and the decision framework.
