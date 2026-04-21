# Research: Sales Follow-Up Cadence Best Practices
*April 2026*

## Stage-Based Cadence Rules — Industry Best Practices

### Framework recommendations

**HubSpot's "Sales Cadence" research (2023)** — four standard tempo tiers:

| Stage | Recommended Touch Frequency | Channel Mix |
|-------|----------------------------|-------------|
| New/Inbound (hot) | Day 1, Day 3, Day 7 | Call + email + text |
| Active/Engaged | Every 5–7 business days | Call primary, email backup |
| Nurturing/Long-horizon | Every 21–30 days | Email primary, call every 2nd touch |
| Dormant/Stalled | Every 45–90 days | Email only, single re-engagement attempt per quarter |

**Salesforce's "State of Sales"** distinguishes between velocity-based cadence (consumer SaaS, fast close) and relationship-based cadence (complex B2B, long cycles). For complex deals over 60-day sales cycles, the recommendation shifts to **calendar-anchored** follow-up rather than fixed-interval: "Follow up when something meaningful can be said, or when the prospect's situation may have changed."

**Gong's analysis** of 300,000+ B2B sales calls found that top performers do not follow the same cadence for all prospects. They apply **signal-weighted frequency** — increasing contact on accounts showing buying signals and decreasing contact when signals go quiet. The worst performers followed rigid day-based sequences regardless of engagement.

**The SPIN Selling and Challenger frameworks** argue cadence should be driven by where the prospect is in their buying process, not the seller's pipeline stage. Challenger Sale specifically warns against "check-in calls" as they signal low value and train prospects to ignore the rep.

### For complex B2B (Golden Eagle context)
Jeff Parmeter's sequence (1 week → 30 days → 3 months) is essentially the academic standard for complex B2B. Lucas's weekly/monthly/quarterly split matches. The gap is not the cadence logic itself — reps already know the right intervals. The gap is enforcement.

---

## The Daily Prioritization Problem

### Three documented approaches

**1. Most Overdue First ("Aging Report" model)**
Simple, transparent. Weakness: treats a contact 8 days overdue for a 7-day follow-up the same as one 8 days overdue for a 90-day follow-up. Blunt instrument without normalized urgency.

**2. Highest Value First**
Weighted by deal size, close probability, or stage value. Primary weakness at 100 contacts: degrades to "always call the 5 hot ones and ignore everyone else." Does not solve the 85-contact problem.

**3. Signal-Driven Prioritization (Gong, Outreach, Salesloft model)**
Surfaces contacts based on behavioral signals: email opens, website visits, trigger events. Requires behavioral data infrastructure. However, Sundial's AI extraction of action items from call transcripts is a lightweight version — surfacing signal from conversation content rather than clickstream data.

**4. Next Due Date + Temperature Hybrid (practical mid-market standard)**
Most common model in mid-market CRMs (HubSpot, Pipedrive, Close.io):
1. Overdue first (hardest deadline)
2. Then by stage temperature (hot > warm > cold) within overdue
3. Then by next due date for upcoming

**Morning sprint model (mature inside sales orgs):**
- 7:30–9:00am: review today's list (CRM-generated, sorted by urgency)
- 9:00–11:30am: outreach block (calls first, emails second)
- Afternoon: reactive (inbound, active client work)

---

## Touch Frequency Research — When to Give Up

**RAIN Group** ("Top Performance in Sales Prospecting," n=489 B2B buyers):
Average touches to reach a prospect who ultimately buys: **8 touches**. Most reps quit after 2.

**Velocify / Ellie Mae** (mortgage/housing industry specifically):
Reps who made **6+ contact attempts** converted at 70% higher rates. For inbound leads that did not convert in the first call, highest conversion windows: Day 1, Day 3–5, Day 14, and Day 30.

**InsideSales.com / Xant** (Harvard Business Review partner study):
Response rates drop dramatically after the 6th touch. 90% of first-time meetings generated within the first 6 touches. After 6 unanswered attempts over 30 days with no signal, continued outreach has <2% incremental yield.

Jeff Parmeter's documented practice — disqualifying after 6 unanswered attempts — is directly aligned with this research.

### Touch count by temperature

| Temperature | Recommended Touch Cap Before Disqualification Decision |
|-------------|-------------------------------------------------------|
| Hot (inbound, engaged, near-term) | 6–8 touches over 30 days |
| Warm (inbound, interested, 6–24 month horizon) | 4–6 touches over 90 days |
| Cold (in database, no engagement, 2+ year horizon) | 2–3 touches per quarter, indefinite |

---

## Nurturing at Scale — The 85-Contact Problem

### The documented failure mode
When a rep has 15 hot prospects and 85 nurturing contacts:
- The 15 hot contacts get appropriate attention
- The top 10–15 nurturing contacts (recently active, close to moving) get sporadic attention
- The remaining 70+ get functionally forgotten — touched only when the rep notices the aging report is red

Research from HubSpot and Gong shows reps with 100+ contacts actively work an average of only **22 contacts** at any given time.

### Best practices for managing dormant contact volume

**1. Batched nurture days**
Designate fixed windows per week for nurture outreach — not a daily rolling review. E.g., "Nurture block: Tuesday 2–4pm and Friday 1–3pm." Prevents nurturing from being perpetually pre-empted by hot work.

**2. Template-first, personalize-second**
Reps who write every nurture email from scratch average 8–12 minutes per email. Template-first workflows (write once, personalize one sentence) drop this to 2–3 minutes. At 85 contacts, the difference between a 7-hour nurture day and a 3-hour one.

**3. Content-triggered vs. calendar-triggered**
Calendar-triggered nurture creates uniform cognitive load every month. Content-triggered nurture ("email all mid-funnel prospects when the new YouTube home tour drops") creates natural batches with a legitimate reason to reach out. RAIN Group found content-triggered outreach has **3–4x the response rate** of check-in calls.

**4. Tiered nurture (not binary active/nurturing)**
- **Warm nurture**: 3–4 week cycle, personalized emails, occasional call
- **Cool nurture**: 6–8 week cycle, content-only emails
- **Maintenance**: quarterly check-in, largely templated

A single "Nurturing" bucket creates false equivalence between a prospect who called last month and one who was contacted two years ago.

---

## Transition Triggers — What Moves Contacts Between Stages

### Nurturing → Active (upgrade triggers)

| Signal | Source | Automation Feasibility |
|--------|--------|----------------------|
| Prospect finds/buys land | Rep-reported, extracted from call | Manual or AI extraction |
| Explicit timeline acceleration ("we want to break ground this spring") | Extracted from call transcript | AI extraction — Sundial can do this |
| Budget confirmation | Rep-reported | Manual |
| Repeat inbound contact after dormancy | System-detectable | Automatable |
| Life event (retirement, business sale, inheritance) | Extracted from call | AI extraction |

**For Golden Eagle specifically:** the dominant trigger is **land acquisition**. John Wednt uses the two-year planning horizon as his qualification threshold. The land question is a hard binary — no land = long-horizon nurture, has land = active. This needs to be a structured field, not buried in notes.

### Active → Closed/Lost (downgrade triggers)

| Signal | Standard Practice |
|--------|-----------------|
| Explicit disinterest ("going with someone else") | Manual close/lost, rep-driven |
| Non-response after 6+ attempts | Manual disqualification prompt after threshold |
| External kill factor (financing denied, land lost, divorce) | Manual close/lost |

**Manual vs. automated:** Research consensus is system-prompted but rep-confirmed. Fully automated stage changes have a documented failure mode — reps stop trusting the pipeline data. Best practice: system-generated prompts ("this contact may need a stage review") with a one-click confirm.

---

## What Breaks at Scale

### 50 contacts: manageable chaos
Mental tracking is straining but survivable. Aging report provides a reasonable safety net. Failure modes are individual errors.

### 100 contacts: system failure without infrastructure
The mental model breaks under normal conditions and collapses entirely under high-volume days. Documented failure modes:
- **The hot-pocket effect**: All rep attention concentrates on the top 10–15 contacts. Studies from InsideSales.com show reps with 100+ contacts actively work an average of 22 contacts at any given time.
- **Stale data compounding**: Without forced updates, CRM data ages. Reps are reluctant to open a contact they haven't touched in 6 months.
- **Reminder system abandonment**: When setting reminders is manual, reps progressively stop setting them for lower-priority contacts.

### 200 contacts: system collapse
Average actual contacts worked per week: 35–45 out of 200. Contacts with zero touch in previous 60 days: typically 40–60% of the total book. The cure at this scale is full automation: sequencing platforms that queue calls and emails automatically.

Golden Eagle's reps are at 100 contacts today. YouTube growth and expanding product complexity suggest 150–200 contacts per rep is coming. The system built now should survive that without requiring rep-initiated automation at every step.

---

## Synthesis: Implications for Sundial Phase 9+

### What the reps are doing right (preserve this)
- Jeff's 1-week / 30-day / 3-month cadence logic is industry-standard for complex B2B
- The hot/active/nurturing mental tiering is correct — needs to be system-enforced
- Lucas's content-triggered nurture (YouTube drops) is a best practice — should be a first-class feature
- Jeff's disqualification trigger at 6 no-responses matches research

### What the system needs to add
1. **System-generated daily prioritization list** — sorted "today's work" view: overdue first, then by temperature, then upcoming
2. **6-attempt disqualification prompt** — automated threshold detection surfacing a modal: "Maintain or disqualify?"
3. **Land acquisition as a structured field** — not buried in notes; the single most important stage-transition signal for Golden Eagle
4. **Content-drop batch nurture trigger** — when Jay releases a new video, surface "15 nurturing contacts haven't been touched in 14+ days — draft a batch check-in?"
5. **Sub-tiers within Nurturing** — or at minimum, sort the Nurturing list by `next_follow_up` date ascending
6. **AI-extracted transition signals** — extract stage-relevant signals from transcripts: "prospect mentioned they're closing on land next month" → flag for stage review

### What not to build yet
- Email sequencing automation (rep trust/adoption risk)
- Behavioral signal tracking (requires infrastructure Golden Eagle doesn't have)
- Hard automated stage transitions (reps stop trusting the data)

Research consistently shows **prompted but rep-confirmed** is the highest-adoption model for teams transitioning from fully manual cadence. Fully automated systems have 3–4x higher rep rejection rates in the first 90 days.
