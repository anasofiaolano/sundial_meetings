# Quickstart Guide — Epoch Methodology

This guide walks you through setting up and using the epoch methodology for a new project. No prior knowledge required.

---

## What You'll Need

- A Claude Code session (or any AI agent with file creation capability)
- A project idea (what you want to build)
- Time to review decks and provide feedback at checkpoints

---

## Step 1: Set Up the Project Folder

Copy the methodology files into your project directory:

```
your-project/
├── CLAUDE.md                    ← Copy from the methodology's CLAUDE.md
├── 00-GUIDELINES.md             ← Copy from the methodology's 00-GUIDELINES.md
├── 01-EPOCHS/
│   └── EPOCH-TEMPLATE.md        ← Copy from the methodology
├── 02-SCOPE-OF-WORK.md          ← Starts blank (agent creates during Phase 2)
├── 03-WORKSTREAMS/
│   └── WORKSTREAM-TEMPLATE.md   ← Copy from the methodology
├── 04-STATE.md                  ← Copy the template
├── 05-DECISION-LOG.md           ← Copy the template
├── 06-TESTS.md                  ← Starts blank
├── 07-PRESENTATION.md           ← Starts blank
├── 08-QUICKSTART.md             ← This file (optional — for reference)
└── TEMPLATES/
    ├── deck-template.html       ← Copy from the methodology
    ├── spec-template.md         ← Copy from the methodology (team mode only)
    └── report-template.md       ← Copy from the methodology (team mode only)
```

The agent reads `CLAUDE.md` automatically on session start. That file tells it everything it needs to know.

---

## Step 2: Tell the Agent What to Build

Start a Claude Code session in your project directory and describe what you want to build:

> "I want to build [description of your project]."

The agent will:
1. Read CLAUDE.md and GUIDELINES.md (automatic)
2. Determine the right preset for your project (Full, Light, or Skip)
3. Ask if you want solo mode or team mode

**For complex projects:** Say "spin up the team" to get a Manager + Builder pair. The Manager enforces the methodology and sequences the work. The Builder implements.

**For simpler projects:** The agent works solo. Same methodology, less overhead.

---

## Step 3: Review Epoch Decks

The agent will NOT jump straight to code. Instead, it designs first:

**Epoch 1:** The agent maps out the happy path and does a flow explosion (mapping ALL possible flows, not just the obvious ones). It produces an HTML deck for you to review.

**Your role:** Open the deck in your browser. Look for:
- Are the flows complete? Did it miss any user journeys?
- Are the tool/technology choices right?
- Are there failure modes it didn't consider?
- Anything from your domain knowledge that the agent wouldn't know?

**This is your highest-value contribution.** The agent is an expert coder but doesn't have your context about the business, the users, or the deployment environment. Your feedback here prevents weeks of wasted work.

Tell the agent what to change. It will incorporate your feedback into the next epoch.

**Epoch 2:** A hardened version incorporating evaluation research and your feedback. Another deck, another review.

**When to stop:** The agent checks convergence criteria. Usually 2-3 epochs is enough. You can also say "good enough, let's proceed" at any point.

---

## Step 4: Confirm the Scope

After epochs converge, the agent produces a Scope of Work — a summary of what will be built, what's out of scope, and the key technical decisions. You'll get a deck.

**Your role:** Review and confirm. This is the contract before coding begins. If something is wrong, now is the time to say so.

---

## Step 5: Let It Build

The agent chunks the work into parallel workstreams and starts implementing. During this phase:

- The agent updates STATE.md after every action (so it can recover if context compacts)
- The agent logs decisions in DECISION-LOG.md (so you can understand the "why" later)
- The agent may flag items with 🚨 if it needs your input before proceeding

**Your role during build:** Mostly hands-off. The agent will ask if it hits a decision it can't make alone. You can check STATE.md anytime to see current progress.

---

## Step 6: Run the Tests

When the build is complete, the agent produces:
- **PRESENTATION.md** — a plain-language summary of what was built
- **TESTS.md** — step-by-step test cases you can execute

**Your role:** Run the tests. The agent can't manage multiple browser windows or test deployment environments — that's your job. Report results back.

---

## Your Role at Each Phase

| Phase | What the Agent Does | What You Do |
|-------|-------------------|-------------|
| **Epochs** | Designs architecture, maps flows, researches best practices | Review decks, provide domain knowledge, approve or request changes |
| **Scope** | Produces scope document | Confirm it's right — this is the contract |
| **Workstreams** | Chunks work into parallel streams | Review the plan (optional but recommended) |
| **Build** | Implements everything, logs decisions | Mostly hands-off. Respond to 🚨 flags. Check STATE.md for progress. |
| **Deliver** | Produces presentation + test cases | Run tests, verify the build works |

---

## Choosing the Right Preset

| If your project is... | Use... | What happens |
|----------------------|--------|--------------|
| A complex new feature or system | **Full mode** | 2-3 epochs, scope confirmation, multiple workstreams, full test suite |
| A bug fix, refactor, or small enhancement | **Light mode** | 1 epoch (abbreviated), straight to build, focused tests |
| A trivial change (≤3 files, <30 min) | **Skip** | Straight to build, still logs decisions |

The agent determines this automatically, but you can override: "Use full mode for this" or "This is just a quick fix, use light mode."

---

## Tips for Getting the Most Value

1. **Front-load your context.** The more you tell the agent upfront about your business domain, deployment environment, and constraints, the better the first epoch will be.

2. **Review decks carefully.** Your highest-value contribution is at the epoch review stage. A correction here saves days of implementation work.

3. **Share what you know about failure modes.** The agent is good at finding technical failure modes. You're better at finding business logic failures, edge cases from real users, and deployment environment gotchas.

4. **Don't skip the flow explosion.** It's tempting to say "just build the happy path." The flow explosion is where the agent discovers 80% of the bugs that would otherwise ship to production.

5. **It's OK to say "good enough."** The convergence criteria exist to prevent over-engineering. If the agent is on epoch 3 and you're satisfied, say "proceed to scope."

6. **Check STATE.md when you return.** If you step away and come back, STATE.md tells you exactly where things stand in 30 seconds.

---

## If Something Goes Wrong

| Problem | What to Do |
|---------|-----------|
| Agent jumped straight to code | Say "Stop. We need to do epochs first." It will course-correct. |
| Agent is over-engineering | Say "This is a Light mode project" or "Good enough, proceed." |
| Agent seems confused after compaction | It should read STATE.md automatically. If not, say "Read STATE.md and resume." |
| Architecture feels wrong mid-build | Say "Stop. We need a mid-build epoch." The agent will halt and create a new epoch. |
| Agent isn't flagging decisions for review | Say "I want to review [X] before you proceed." |
| You disagree with a technical decision | Review the tradeoff table in DECISION-LOG.md and explain your reasoning. The agent will adapt. |

---

## Quick Summary

1. **Copy the template files** into your project folder
2. **Tell the agent** what you want to build
3. **Review decks** at each checkpoint (this is your highest value-add)
4. **Confirm scope** before coding begins
5. **Let it build** (check STATE.md for progress)
6. **Run the tests** when it's done
