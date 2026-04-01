# Guidelines — Staff Engineer Principles

*Mandatory reading on every session start. Consult again during decisions.*
*These are not aspirational — they are requirements.*

---

> **Living reference:** The engineering principles in this file are based on a living document at `/Users/anaolano/Desktop/CODE/_MY_GUIDELINES/ENGINEERING_PRINCIPLES.md`. On session start, check if that file has been updated with new principles — if so, incorporate them here. This file may lag behind the source.

## Part 1: Engineering Principles

These principles apply to every project. Run through this list during epoch design, flow explosions, and before writing code. When reviewing existing code, use this as a checklist.

### 1. Every State Needs an Exit Path

**The principle:** When designing any flow, sequence, or state machine, explicitly map every possible state a record can be in and ask: *"How does a record get OUT of this state?"* If you cannot answer that, you have a potential limbo bug.

**Why it matters:** Records that get stuck in an intermediate state are invisible to the system. No error is thrown, no alert fires, no job fails. They just sit there forever, silently falling through the cracks.

**How to apply it:**
- Before building any sequence or flow, draw out every state explicitly
- For each state, write down: what moves a record INTO this state, and what moves it OUT
- If any state has no guaranteed exit, add one — either a timeout, a fallback transition, or a manual review flag
- Ask: "what happens if the expected condition never occurs?" (e.g. they never book, they never pay, they never respond)

### 2. Enforce Impossible States at the Database Level

**The principle:** Don't rely on application code to keep data valid. Use database constraints, triggers, and validations to make invalid states literally unwriteable. If a state shouldn't exist, the database should reject it.

**Why it matters:** Application code changes constantly — especially when an AI agent is making edits. The database is the one layer that's always there, always enforced, regardless of what path the data took to get there.

**How to apply it:**
- For every table, ask: "what combinations of field values should never be possible?"
- Use `CHECK` constraints for simple rules
- Use triggers for complex invariants spanning multiple fields or tables
- Think of the database as the last line of defense — if invalid data gets in, everything downstream is compromised

### 3. Own Your Critical Path — Don't Trust Black Boxes

**The principle:** Whenever a critical automation depends on someone else's infrastructure, you are trusting a black box you cannot inspect, cannot fix, and cannot reason about under failure. Write the triggering logic yourself, as close to the data as possible.

**Why it matters:** If a platform's built-in feature has a bug, an outage, or changes its retry behavior — you cannot fix it. You find out when things stop working.

**How to apply it:**
- For any critical event, write the trigger yourself rather than relying on a platform's built-in automation
- Prefer triggering mechanisms closer to the data (DB trigger > application code > third-party webhook)
- Ask: "if this triggering mechanism fails silently, would I know? Can I fix it?"
- Document every external dependency in the critical path and have a plan for each one failing

### 4. Failed Jobs Must Never Disappear Silently

**The principle:** Every automated job needs an explicit failure path. Retry on failure with backoff. After exhausting retries, move to a dead letter queue where a human can inspect and resolve the failure.

**Why it matters:** Silent failures are the most dangerous kind. A job that fails and disappears looks identical to a job that succeeded — until someone complains.

**How to apply it:**
- Use a proper job queue for async work — not cron jobs
- Configure retry counts and backoff for every job type
- Every job queue needs a dead letter queue (with alerts for spikes)
- Periodically review the dead letter queue

**Rate limiting:**
- Every third-party API integration needs rate limiting that respects their documented limits
- Prevent hitting limits, don't just handle the errors after
- Document rate limits in code comments or configuration
- Consider what happens when multiple workflows share the same limit pool

### 5. Alerting Is Not Optional

**The principle:** If something breaks in production and nobody gets notified, it might as well not be monitored. Every critical flow needs an alert path that reaches a human fast enough to matter.

**Why it matters:** A critical failure at 3am should generate a notification before business hours. Not be discovered days later when a user complains.

**How to apply it:**
- For every critical flow, define: "who gets notified if this fails, and how fast?"
- At minimum: a notification to the relevant person on any unhandled error
- Distinguish warning-level vs. critical failures
- Test your alerts — an alert that doesn't fire is worse than no alert

**Execution history:**
- Every automated job needs permanent, searchable execution history (minimum 90 days)
- console.log() is not execution history
- History must include: input parameters, output/result, duration, error messages, retry attempts
- "Did this job run 3 days ago? What was the result?" must be answerable

### 6. Monitor for Impossible States in Production

**The principle:** Even with good validation and constraints, data can get into unexpected states over time. Run regular automated queries that check for records in states that shouldn't exist, and alert when they find something.

**Why it matters:** Constraints prevent bad writes going forward, but they don't fix existing bad data. Edge cases you didn't anticipate will slip through.

**How to apply it:**
- For every flow, write at least one "sanity check" query for impossible or stuck states
- Run on a schedule (daily is usually sufficient)
- Route results to an alert if any records are found
- Good questions: "Active records with no next action?", "Records in this state longer than X days?", "Records missing required fields at this stage?"

### 7. The Audit Trail Is Downstream, Not Upstream

**The principle:** An audit trail is a receipt — it records what happened after the fact. Write to it AFTER a job succeeds, not as the mechanism that triggers jobs. Never use your audit log as an event bus.

**Why it matters:** Using an audit log as a trigger source conflates two responsibilities. The log becomes both a record of truth AND a control surface.

**How to apply it:**
- Trigger automations from the source of truth (the data table that changed), not from a log of changes
- Write to the audit log as the last step of a successful job, not the first step
- Keep event triggers and audit trail as separate concerns

### 8. Agent-Proof Your Core Logic

**The principle:** AI agents are powerful but context-blind at scale. Core business logic — automations, validations, state transitions — should live at the database layer where the agent cannot accidentally overwrite or bypass it.

**Why it matters:** Application-layer code is what the agent reads, edits, and rewrites. If your critical logic lives there, every agent session is a risk. Database-layer logic is invisible to the agent's normal editing workflow.

**How to apply it:**
- Put validations, state transition rules, and core invariants in the database (triggers, constraints, functions)
- Application code should be thin wiring — call the database, render the result
- Maintain an architecture doc the agent reads on session start
- Before asking an agent to build something, check if it already exists — agents build duplicates when they lack context

### 9. Match Your Execution Model to Your Workload

**The principle:** A daemon is for workloads that need to be continuously alive. A cron job is for batch work that runs and exits. Pick the one that matches.

**Why it matters:** When you use a daemon for batch work, you inherit all of the daemon's problems (crash recovery, lock files, orphan state) without needing any of the daemon's benefits.

**The tell:** If your "daemon" has a `time.sleep(60)` in a `while True` loop, it's a cron job wearing a daemon costume.

**How to apply it:**
- Before making something a daemon, ask: "does this need to be alive between units of work?"
- If each cycle reads state, does work, writes state, and carries nothing in memory — it's a cron job
- Use the platform's scheduling primitive rather than reimplementing with `while True` + `sleep`

### 10. A Daemon Has to Handle Its Own Continuity

**The principle:** A daemon promises "I will stay alive and keep working, no matter what." That promise forces it to handle crashes, mid-task failures, duplicate instances, stale connections. Each one is a bug surface. A cron job has none of these problems because each run is independent.

**How to apply it:**
- Audit your daemon for "continuity glue": lock files, PID checks, orphan recovery, reconnection logic
- If most of the complexity is continuity management rather than actual work, the execution model is wrong
- Ask: what happens if I kill this process right now? If the answer requires special cleanup code, that's continuity debt

### 11. Don't Build What the Platform Gives You for Free

**The principle:** Before writing infrastructure code, check if the platform already solves the problem. Your code is always less tested than the OS, the framework, or the managed service.

**How to apply it:**
- Before implementing scheduling, locking, retries, or health checks: check if your platform provides these
- Prefer the platform's version even if it's slightly less flexible — reliability beats customization
- Document where you're relying on platform guarantees

### 12. Monitor "Is Work Flowing?", Not "Is the Process Alive?"

**The principle:** Process liveness is a bad proxy metric. A process can be alive and doing nothing. The right question: are inputs being converted to outputs at the expected rate?

**How to apply it:**
- For every pipeline, define the input→output flow and monitor the conversion
- Measure backlog size and throughput
- Alert when backlog grows or throughput drops to zero
- Silence (no errors, no output, no activity) is itself a signal worth investigating

### 13. Monitor What You Can Predict, Then Add Catch-Alls

**The principle:** Two layers. Specific monitors for failure modes you can enumerate. Catch-all monitors for everything else — metrics that signal "something is off" without diagnosing the cause.

**How to apply it:**
- Write specific monitors for every failure mode you can think of
- Add 2-3 catch-all metrics that measure system health from the outside
- Use multiple catch-all metrics as safety layers to triangulate
- Catch-alls should be simple, cheap to compute, and independent of the failure mode

### 14. Silent Failure Is Worse Than Loud Failure

**The principle:** The worst outcome isn't a crash — it's a system that looks healthy but isn't doing its job. A crash is visible. Silent failure can continue indefinitely.

**How to apply it:**
- Design every automated system to surface failure where the user will see it
- Prefer false alarms over missed failures
- Test: if this system fails right now, how long until a human notices?
- When a system goes quiet, treat silence as a signal

### 15. Conduct a Blind Spot Review

**The principle:** After completing a design, get a fresh perspective with zero anchoring. Spin up a second agent (or reframe as a different engineer in solo mode), give it the full context of what you've planned, and ask: "What am I missing? What would break? What haven't I considered?" That's it. No checklist, no prescribed categories.

**Why it matters:** Cognitive anchoring makes certain failure modes invisible to the original author. A checklist of "things to look for" just gives you back what you already thought of. The value is in what the fresh perspective finds that you didn't think to look for. Real-world evidence: in one production project, a blind spot review caught 3 critical bugs, 6 significant issues, and 4 minor improvements — none visible during normal flow explosion.

**How to apply it:**
- In solo mode: reframe with a fresh-perspective prompt — *"You are a different engineer seeing this architecture for the first time. Here is everything we've planned: [full context]. What's missing? What would break? What haven't we considered?"*
- In team mode: spin up a second agent, give it the full epoch context, and ask the same questions
- Do NOT give the reviewer a checklist or categories — that defeats the purpose
- The reviewer's value is proportional to how little they're anchored by the original author's thinking

---

## Part 2: Methodology Principles

These principles govern how the epoch methodology is applied.

### Architecture First

Don't rush to code. Ask: "What would a staff engineer do?"
- Prefer event-driven over polling when the event source is known
- Prefer triggers over cron when timing is data-dependent
- Database is source of truth; filesystem is not
- The simplest solution that works is the right one — not over-engineered, not under-engineered

### Never Overwrite

History is sacred. When updating any working document:
- Append, don't replace
- Trace decisions: "noticed X → did Y → status: resolved/still open"
- The ONE exception: STATE.md is always overwritten (that's its purpose — hot, current state)

### Failure Modes First

Before documenting the happy path, document what can go wrong:
- Critical risks float to the top of every document — above the overview, above the happy path
- Use `🚨 HUMAN MUST EVALUATE` callouts for decisions requiring human judgment
- Every failure mode needs a mitigation or an explicit "accepted risk" designation

### Organic Growth

Don't try to write the final version upfront. Documents evolve:
- Start with what you know
- Add sections as issues are discovered
- Spawn subphase docs when a subtopic becomes its own distinct problem
- Cross-reference with parent/child links

### Real Tradeoffs

Not: `| Tool | Why This One |`
But: `| | Option A | Option B (chosen) |` with columns specific to the decision (setup time, debuggability, who owns the fix, etc.)
Followed by: `**Decision:** [choice]. [one sentence why].`

### Actionable Instructions

Not: "Update the log after actions"
But: "After completing a task, append to DECISION-LOG.md with: `### [timestamp] — [title]` followed by Did/Why/Files/Impacts."

### Seek a Second Perspective

After documenting failure modes, always conduct a Blind Spot Review (see Principle 15):
- In solo mode: reframe with a fresh-perspective prompt — give full context, ask "what's missing?"
- In team mode: spin up a second agent with full context
- Do NOT prescribe what to look for — fresh eyes means no anchoring
- The goal: catch what cognitive anchoring makes invisible to the original author

---

## Part 3: Engineering Checklist

*Run this during every epoch, flow explosion, and before building anything new.*

### State & Data Integrity
- [ ] What states can this record/entity be in? Does every state have an exit path?
- [ ] What combinations of values should never be possible? Add constraints.
- [ ] Is this logic in a durable layer (DB) or a fragile layer (application code)?

### Ownership & Dependencies
- [ ] Who owns the trigger for this automation? Is it our code or someone else's?
- [ ] Am I reimplementing something the platform already provides?
- [ ] What external dependencies are in the critical path? What if each one fails?

### Failure & Recovery
- [ ] What happens when this job/flow fails? Is there retry logic?
- [ ] Where do permanently failed jobs go? (Dead letter queue, not into the void)
- [ ] Am I writing to the audit log as a receipt (after success) or as a trigger (before)?

### Observability
- [ ] Who gets alerted when this breaks? How fast?
- [ ] What sanity check query would catch if this goes wrong silently?
- [ ] Am I monitoring work flow (inputs→outputs), not just process liveness?
- [ ] Do I have catch-all monitors for failure modes I haven't predicted?
- [ ] If this system fails silently right now, how long until a human notices?

### Execution Model
- [ ] Does this workload need to be a daemon, or is it a cron job?
- [ ] If it's a daemon, what "continuity glue" am I writing? Is there a simpler model?

### Agent Safety
- [ ] Is core logic in the DB layer where agents can't accidentally break it?
- [ ] Does an architecture doc exist for agents to read on session start?
- [ ] Before building something new, have I checked if it already exists?

### Blind Spot Check
- [ ] Have I conducted a Blind Spot Review? (Solo: fresh-perspective prompt. Team: second agent.)
- [ ] Did the reviewer have full context but NO prescribed checklist? (Fresh eyes = no anchoring)
- [ ] What assumptions am I making that might not be true?
- [ ] What would a staff engineer change about this design?

---

## Part 4: Decision Framework

When facing any architectural or tool decision, work through this:

1. **State the problem clearly.** One sentence. What are we solving?
2. **List the options.** At least 2 real alternatives (not a strawman).
3. **Build a comparison table.** Columns specific to the decision, not generic. Include: who owns the fix path, what happens on failure, setup cost, ongoing maintenance.
4. **Make the call.** `**Decision:** [choice]. [one sentence why].`
5. **Record it.** Append to DECISION-LOG.md with the comparison table.
6. **The staff engineer test:**
   - [ ] No circular dependencies
   - [ ] No unbounded loops or recursion
   - [ ] Every external dependency has a failure handler
   - [ ] No single point of failure without recovery
   - [ ] Simplest solution that works
   - [ ] A senior engineer would approve in design review

---

## Part 5: Tool Selection

Before committing to any tool or service:

1. **Is this the right tool for the job?** Don't use a hammer because it's familiar.
2. **Is there something better/simpler?** Research alternatives with deliberate knowledge prompting + web search.
3. **What are the failure modes?** List them. Every tool fails.
4. **How do we handle those failures?** For each failure mode: retry? fallback? alert?
5. **Who owns the fix path?** If it's the vendor, we're trusting a black box. Acceptable for non-critical paths. Not acceptable for critical paths.

---

## Quick Reference

| Principle | One-liner |
|-----------|-----------|
| Exit paths | Every state must have a way out |
| DB constraints | Make impossible states unwriteable |
| Own critical path | Don't trust black boxes for critical logic |
| Silent failures | Failed jobs go to dead letter queue, not void |
| Alerting | If nobody gets notified, it's not monitored |
| Impossible states | Sanity check queries on schedule |
| Audit trail | Receipt after success, not trigger before |
| Agent-proofing | Core logic in DB, not application layer |
| Execution model | Daemon only if you need continuous state |
| Continuity cost | If most complexity is "stay alive" glue, wrong model |
| Platform first | Don't reimplement what the platform provides |
| Work flow | Monitor inputs→outputs, not process liveness |
| Catch-all monitors | Two layers: specific + catch-all |
| Silent failure | Silence is a signal — investigate it |
| Blind spot review | Fresh eyes with full context, no checklist — finds what anchoring hides |
