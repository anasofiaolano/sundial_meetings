# Epoch [N] — [Title]

<!--
  INSTRUCTIONS:
  - Copy this file to create a new epoch: epoch-1-happy-path.md, epoch-2-hardened.md, etc.
  - Sections marked REQUIRED must be filled in. Sections marked OPTIONAL can be skipped.
  - REQUIRED sections have substance requirements — don't just check the box.
  - For epoch 2+: fill in the "Changes" section. For epoch 1: delete it.
  - Never overwrite epoch files. For revisions within an epoch, version the file:
    epoch-2-hardened-v1.md → epoch-2-hardened-v2.md
  - Every epoch gets an HTML deck from TEMPLATES/deck-template.html.
  - ⏸ CHECKPOINT: Human reviews deck before proceeding.
-->

**Status:** [🚧 In Progress | 📋 Review | ✅ Approved]
**Priority:** [🔴 Critical | 🟡 Medium | 🟢 Low]
**Created:** [date]
**Last Updated:** [date]
**Builds on:** [previous epoch file + evaluation, or "none — first epoch"]

---

## 🚨 Critical Risks — REQUIRED (Read Before Anything Else)

<!--
  List risks that could invalidate this architecture.
  If none yet, write "None identified — revisit after flow explosion."
  This section is FIRST because risks discovered later get added here, not buried at the bottom.
-->

1. [Risk description. Mitigation or "🚨 HUMAN MUST EVALUATE"]

---

## Changes from Previous Epoch — REQUIRED (Epoch 2+) / DELETE for Epoch 1

<!--
  For epoch 2+: summarize what changed and why.
  Use a comparison table, not prose.
-->

| Area | Previous Epoch | This Epoch | Why |
|------|---------------|------------|-----|
| [area] | [old approach] | [new approach] | [reason for change] |

---

## What the User Wants — REQUIRED

<!--
  Plain language. One paragraph max. What problem are we solving?
  For non-software projects, adapt: "What outcome is the user trying to achieve?"
-->

[Description]

---

## Architecture / Happy Path — REQUIRED

<!--
  How it works when everything goes right. Step by step.
  For non-software: "How the process works when followed correctly."
-->

### Components
<!--
  For software: services, databases, APIs, etc.
  For non-software: concepts, principles, artifacts, stakeholders.
-->

- [Component 1] — [purpose]
- [Component 2] — [purpose]

### Happy Path Flow

1. [Step 1]
2. [Step 2]
3. [Step 3]

---

## Flow Explosion — REQUIRED

<!--
  Map ALL possible flows, not just happy path. This is mandatory.
  For non-software: map user journeys, edge cases, exception paths.
  Keep adding flows until you've exhausted all branches.
-->

### Decision Points

| Point | Branches | What Triggers Each |
|-------|----------|-------------------|
| [decision] | [branch A, branch B] | [conditions] |

### Input Variants

| Input | Valid | Invalid | Edge Cases |
|-------|-------|---------|------------|
| [input] | [variants] | [variants] | [variants] |

### External Dependencies

| Dependency | Happy Path | Fails | Times Out | Returns Unexpected |
|------------|-----------|-------|-----------|-------------------|
| [dep] | [behavior] | [handling] | [handling] | [handling] |

### All Flows Discovered

1. **Flow: [Name]** — [description]
   - Trigger: [what causes this]
   - Steps: [1, 2, 3...]
   - End state: [outcome]

2. **Flow: [Name]** — [description]
   - Trigger: [what causes this]
   - Steps: [1, 2, 3...]
   - End state: [outcome]

*Add flows until all branches are exhausted.*

---

## Tool / Pattern Decisions — REQUIRED

<!--
  Real tradeoff tables, not "Why This One" columns.
  Columns should be SPECIFIC to the decision being made.
  Include: who owns the fix path, what happens on failure.
-->

### [Decision: e.g., "Database choice" or "Scheduling approach"]

| | Option A | Option B (chosen) |
|---|---|---|
| [criterion specific to this decision] | [value] | [value] |
| [criterion specific to this decision] | [value] | [value] |
| Who owns the fix path | [answer] | [answer] |
| What happens on failure | [answer] | [answer] |

**Decision:** [choice]. [one sentence why].

---

## Failure Modes — REQUIRED

<!--
  Fill AFTER happy path. Every failure mode needs a mitigation
  or an explicit "accepted risk" designation.
-->

| Failure Mode | Likelihood | Mitigation |
|---|---|---|
| [failure] | [High/Medium/Low] | [mitigation or "Accepted risk: [reason]"] |

---

## Engineering Principles Review — REQUIRED

<!--
  Run through the GUIDELINES.md engineering checklist against THIS epoch's architecture.
  Don't just check boxes — write brief notes for each.
  Reference: 00-GUIDELINES.md Part 3: Engineering Checklist
-->

### State & Data Integrity
- [ ] What states can entities be in? Every state has an exit path?
- [ ] Impossible state combinations identified? Constraints planned?
- [ ] Core logic in a durable layer (DB) or fragile layer (app code)?

### Ownership & Dependencies
- [ ] Who owns the trigger for each automation?
- [ ] Reimplementing anything the platform provides?
- [ ] External dependencies in critical path listed with failure plans?

### Failure & Recovery
- [ ] Retry logic for failures? Dead letter queue for permanent failures?
- [ ] Audit trail as receipt (after success), not trigger (before)?

### Observability
- [ ] Alert paths defined for critical flows?
- [ ] Sanity check queries for silent failures?
- [ ] Monitoring work flow (inputs→outputs), not just process liveness?
- [ ] Catch-all monitors for unpredicted failure modes?

### Execution Model
- [ ] Each workload matched to the right execution model (daemon vs cron vs event)?

### Agent Safety
- [ ] Core logic in DB layer where agents can't break it?
- [ ] Architecture doc exists for agents to read on session start?

---

## Blind Spot Review — REQUIRED

<!--
  After completing the flow explosion and engineering review, get a FRESH perspective.
  The value is in what the reviewer finds that you DIDN'T think to look for.
  DO NOT give the reviewer a checklist or categories — that anchors them
  to what you already considered and defeats the entire purpose.
-->

**Review method:** [Solo: fresh-perspective prompt | Team: second agent review]

**Prompt used:**
<!--
  Solo: "You are a different engineer seeing this architecture for the first time.
  Here is everything we've planned: [full context]. What's missing? What would break?
  What haven't we considered?"

  Team: Give the second agent the full epoch context and ask the same questions.
-->

[Paste the prompt you used]

### Findings

[What the fresh perspective found — or "No issues found" with brief explanation]

---

## Convergence Check — REQUIRED (Epoch 2+) / OPTIONAL for Epoch 1

<!--
  Check whether the architecture has converged.
  All 5 criteria must be met to proceed to scope confirmation.
  Hard cap: 4 epochs. If not converged by epoch 4, split the project.
-->

| Criterion | Status | Notes |
|-----------|--------|-------|
| All flows have documented handling | [✅/❌] | [details] |
| No unresolved failure modes | [✅/❌] | [details] |
| Delta from previous epoch < 20% | [✅/❌/N/A for epoch 1] | [details] |
| Staff engineer checklist passes | [✅/❌] | [details] |
| Human sign-off | [⬜ Pending] | |

**Staff engineer checklist:**
- [ ] No circular dependencies
- [ ] No unbounded loops or recursion
- [ ] Every external dependency has a failure handler
- [ ] No single point of failure without recovery
- [ ] Simplest solution that works
- [ ] A senior engineer would approve in design review

**Verdict:** [Converged → proceed to scope | Not converged → epoch N+1 needed because... | Epoch 4 reached → split project]

---

## Iteration Notes — OPTIONAL

<!--
  What needs to change for the next epoch? Only relevant if not converged.
-->

- [Observation] → [Proposed change]

---

## Next Steps

- [ ] Happy path documented
- [ ] Flow explosion complete
- [ ] Tool decisions with tradeoff tables
- [ ] Failure modes identified with mitigations
- [ ] Engineering principles review complete
- [ ] Blind spot review complete
- [ ] HTML deck produced from template
- [ ] ⏸ CHECKPOINT: Human reviews deck
- [ ] Convergence check (epoch 2+)
