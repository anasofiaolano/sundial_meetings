# Pipeline & Follow-Up Management — UX Specification

## Design Philosophy
"What do I do next?" — the app answers this question within 2 seconds of opening.

## View 1: Today (the morning screen)

Top bar — one line of plain English:
> Monday, April 6 — 14 actions today / 3 overdue / 2 hot leads need you

Progress bar fills as rep completes actions.

### The Queue
Vertical stack of contact cards sorted by urgency. No tabs, no filters by default.

Priority bands (colored left borders):
- OVERDUE — red border
- TODAY — amber border
- THIS WEEK — gray, recessed

Each card (collapsed):
- Left: Temperature dot + Name
- Center: Why this contact ("32 days since last call — waiting on property survey")
- Right: Call / Email / Snooze / Done buttons
- Subtitle: Location / Project type / Stage

Expanded (tap): Last touch, key context, rapport hooks, suggested action, stage indicator, non-response count.

Completion flow: Done → "How did it go?" → Connected/Left message/No answer → note → card out, next auto-schedules.

At 6 non-responses: Card changes to dashed border, "Disqualify?" prompt with reason picker.

Soft-touch banner for YouTube videos:
> New video: "Choosing the Right Log Profile" — 6 contacts would benefit. Send to all / Review list

## View 2: Pipeline (the big picture)

Compressed kanban — three zones:
- Funnel (narrow): New Lead + Discovery — collapsed count badges
- Active Pipeline (wide): Ballpark → DSA → Design → Materials — standard kanban cards
- Closing (narrow): Contract + Build — cards with progress bars

Stuck indicators: Card border green → amber (1.5x duration) → red (2x).

Stage transitions: Semi-automatic. Toast confirmations on detected events.

Long-horizon contacts: Separate "Nurture Pool" tab. Trigger-date banners surface on main view.

Revenue bar: Single horizontal stacked bar showing value per stage + $4.7M target tick.

Health counter in nav: 3 red, 5 amber.

## View 3: Contact Detail (pre-call screen)

Two columns: left (60%) reference, right (40%) conversation fuel.

Header strip: Name, location, stage, temperature, days since touch, "Call Now" button.

Right column "Before You Call" briefing (15-second read):
- Last conversation summary
- Open questions (unanswered from co-pilot)
- Rapport hooks (personal details)
- What's new (videos, pricing changes)
- Suggested talking points

Below: Rapport notes — freeform, always visible.

Left column:
- Timeline (reverse-chrono, expandable entries, co-pilot transcript links)
- Project details (location, budget, sqft, style, floor plan version)
- Files & attachments (thumbnail grid, drag-to-upload)
- Follow-up schedule (countdown, history, snooze/disqualify)

## View 4: Post-Call Review

Appears after co-pilot call ends. Five collapsible sections:
1. Call Summary (3-5 auto-generated bullets, editable)
2. Action Items (checklist with due dates)
3. Follow-Up Email Draft (pre-composed, editable, send button)
4. CRM Preview (notes, reminder, status change, rapport notes — all editable)
5. Full Transcript (collapsed by default)

Primary action: "Approve All & Save" sticky footer. Target: under 90 seconds.

## Co-pilot Integration
After each call, co-pilot outputs feed into pipeline:
- Transcript → timeline
- Questions → "Open questions" on contact card
- Client details → project details
- Personal details → rapport notes suggestions
- Action items → Today queue

Rep reviews and approves. Nothing auto-saves without confirmation.

## Visual Design
- Light mode default (dark as option)
- Inter / system sans-serif
- Warm neutrals base, amber accent for actions
- Cards: 12px radius, subtle shadow, 24px padding
- 200ms crossfade animations, calm UI

## Sales Process Stages
1. New Lead
2. Discovery
3. Ballpark (~10% accuracy estimate)
4. Design Service Agreement ($4/design sq ft, $20K+ deposit)
5. Design Iteration (5-6 floor plan revisions)
6. Materials Proposal (detailed pricing)
7. Contract (signed, materials ordered)
8. Build (materials shipping until last delivery)
