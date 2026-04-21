# Research: Superhuman UX Patterns
*April 2026*

## The Core Triage Loop

Superhuman's fundamental triage loop is built around a single question posed during onboarding: **"Is this message for today, for another day, or is it done?"**

The mechanical flow:
- You land on the first unread email. The email is already open — you never click to open it.
- You read it. Three paths:
  - **Done now** — press `E`. Archived instantly. Next email slides into view automatically. No return to list.
  - **Action needed later today** — press `J`. Leaves the email in inbox, moves cursor to next.
  - **Defer** — press `H`. Snooze picker appears. Email disappears and resurfaces at specified time.

**Critical UX detail:** After `E`, there is no list view return. The next email slides in automatically. You are always looking at the content of a message, never at a folder. This "conveyor belt" motion creates the triage flow state.

---

## Keyboard-First Design

Designed to be operated entirely without a mouse. Rahul Vohra: "Don't touch your mouse — this is key to getting through your inbox twice as fast."

### Essential single-key triage shortcuts

| Key | Action |
|-----|--------|
| `E` | Mark done / archive (most important) |
| `H` | Remind me / snooze |
| `J` | Next conversation |
| `K` | Previous conversation |
| `R` | Reply |
| `Cmd+Shift+Enter` | Send & Mark Done (send + archive in one gesture) |
| `Cmd+K` | Command palette — any action via text |

The `Send & Mark Done` shortcut is critical: reply+archive costs exactly as many keystrokes as reply alone would in Gmail. There's no second action.

### How shortcuts chain into flow state

```
[Read] → E → [Next email auto-loads] → R → [Type reply] → Cmd+Shift+Enter → [Next email auto-loads] → H → [Pick time] → [Next email auto-loads]
```

---

## Inline Triage Actions (Without Opening Email)

- **Auto-summarize line**: AI-generated one-line summary above every conversation in the list. Assess the email without opening it.
- **Instant Reply drafts**: Three precomputed reply drafts appear below each conversation. Select with `Tab` + `Enter` and send without composing.
- **One-key archive (`E`)**: Fires from the list view without opening the email.
- **One-key snooze (`H`)**: Same — no need to open.
- **Bulk actions**: Select multiple with `X`, apply `E`, `H`, `L` etc. to all at once.

---

## The "Done" Feeling — Engineered Satisfaction

Vohra draws from game design theory: **"The experience of fun can be defined as 'pleasant surprise.'"**

**a) Instant-advance after archiving**
When you press `E`, the archived email vanishes and the next one occupies the same position on screen in 1-2 rendered frames (under 32ms). Power users describe this as "flow state."

**b) The inbox zero completion screen**
When you archive the last email, Superhuman replaces the inbox with a **full-screen photograph** — landscapes, wildlife, seascapes. Carefully curated imagery. On mobile, all UI chrome is hidden.

This is not accidental decoration. The image functions as a **variable reward**. Because the image changes each time, you don't know what you'll see. The unpredictability of the reward amplifies the dopamine response compared to a static "Inbox Zero" message.

**c) Weekly streaks**
Tracks your inbox zero streaks — a lightweight commitment mechanic.

**d) Send & Mark Done in one keystroke**
Compose a reply, send it, watch the email vanish from your inbox in a single gesture.

**e) The onboarding session itself**
Every new user gets a mandatory 30-minute 1:1 video call with an "Onboarding Specialist." The coach guides you to inbox zero during the call. This manufactured first win creates an emotional anchor for the product's promise.

---

## Snooze / Remind Later ("Remind Me")

Shortcut: `H`

**Preset options:**
- Later today
- Tomorrow morning (default 8am, configurable)
- This weekend
- Next week
- In 2 weeks
- Custom date/time

**Natural language input:** Type `3d`, `1mo`, `48hrs`, `next tuesday 9am` — Superhuman parses it. No calendar widget required.

**Two reminder modes:**
- **"If no reply"** (default): Reminder only fires if nobody has replied to that thread. If someone replies, the reminder is cancelled. Prevents duplicate notifications for active threads.
- **"Regardless"**: Fires at specified time no matter what.

**Auto Reminders:** Automatically suggests reminders for emails detected as "sent but unanswered." If you send an email and don't get a reply within your configured follow-up window, it automatically adds a reminder without you having to set one.

---

## Split Inbox

The inbox is divided into named splits, navigable via `Tab`/`Shift+Tab`. Each split is defined by a Gmail filter.

**Default split structure:**
- Important
- Other
- Custom splits: VIPs, Team, Newsletters, Notifications, Cold Outreach

**Why this creates speed:** When you open the "Newsletters" split, your brain shifts into a lighter, faster, more aggressive archiving mode. When you open "Important," you're in a more focused, deliberate reading mode. The cognitive switch is intentional.

**Recommended: 3-7 splits.** Too few defeats the purpose; too many creates "too many places to check."

---

## Speed: Specific Technical and Design Decisions

**Paul Buchheit's 100ms rule:** Any interaction that completes in under 100ms feels instantaneous. Superhuman targets under 50ms for most interactions; new renderer hits 1-2 Chrome frames (under 32ms) for email display.

**Preloading adjacent emails:** As you read one email, Superhuman is already fetching and rendering the next one. When you press `E`, the next email is already in memory.

**Precomputed AI drafts:** Instant Reply drafts are generated before you open the email. Unlike Gmail's "Help me write," there's no wait time.

**Offline-first architecture:** All email content is cached locally. Search is local-first. Eliminates network round trips.

**Minimal animations:** Almost no animations. Every triage action is a cut, not a fade or slide. Animations consume perceived time even when they're fast.

**Typography as speed:** Six months selecting and modifying the typeface (Adelle Sans), optimizing letterform spacing and weight for email addresses and names — the most common content in subject lines. Readable typography means fewer re-reads.

**The 100ms rule as a filter for features:** Any feature proposal that would add perceptible latency is cut or deferred.

---

## The AI Layer

**Auto Summarize:** One-line summary above every conversation in the inbox list. Passive — it's just there. "The first Superhuman AI feature you don't have to remember to use."

**Instant Reply:** Three precomputed full-email reply drafts below each conversation. Generated before you open the email. Match your writing voice (trained on your sent history). Users write emails twice as fast and reply to emails they would previously have ignored.

**Write with AI (`Cmd+J`):** Type a short prompt, Superhuman drafts the full email. Quick edits: Improve writing, Fix spelling, Shorten, Lengthen, Simplify. Users average 37 invocations per week.

**AI Search (`Shift+/`):** Semantic search that understands intent. "The email from the investor about the Series B term sheet" finds the right thread even without exact keywords.

**Auto Labels:** AI automatically categorizes incoming mail into custom-defined buckets. ~94% accuracy after approximately two weeks of learned behavior.

---

## Design Principles (from Rahul Vohra)

### "Game Design, Not Gamification" — five factors

1. **Goals** — must be concrete, achievable, and rewarding. Inbox zero is the goal. It must be possible to actually reach it.
2. **Emotions** — software should provoke emotional responses, not just complete tasks. The inbox zero photo exists purely to make you feel something.
3. **Flow** — the psychological state where challenge matches skill (Csikszentmihalyi). Superhuman designs every interaction to keep you in flow: no context switches, no mode changes, no mouse.
4. **Controls** — interaction design should feel natural and responsive. The 100ms rule is a controls principle.
5. **Toys** — elements that are satisfying to manipulate independent of the goal. The keyboard shortcuts themselves are "toys."

**Explicit distinction:** Gamification uses extrinsic rewards (badges, points) which destroy intrinsic motivation. Stanford research showed children who were given rewards for drawing spent half as much time drawing afterward. Superhuman instead makes the core act of processing email intrinsically satisfying.

**"Single decisive attribute":** Speed is Superhuman's single decisive attribute. All product decisions are filtered through this lens.

**"The natural path through the inbox is also the fastest path."** There's no shortcut you have to remember to use to be efficient — the default behavior is already optimized.

---

## What a Power User's Daily Session Looks Like

1. Open Superhuman (loads instantly, locally cached). Land directly on first unread email in "Important" split.
2. Auto-summarize line is already visible. Scan it. Decide in ~2 seconds.
3. If it needs a reply: check three Instant Reply drafts. If one is close, `Tab` to select, edit inline, `Cmd+Shift+Enter` to send and archive. Total: 10-20 seconds.
4. If it needs no reply: `E` to archive. Next email immediately appears. Total: 1 second.
5. If it needs to wait: `H`, type "tomorrow 8am" or press preset, `Enter`. Next email immediately appears. Total: 3 seconds.
6. Repeat until "Important" is empty. The inbox zero photo fills the screen. A beat of satisfaction.
7. `Tab` to next split. Repeat.
8. By "Newsletters" you're in aggressive-archive mode: scanning one-line summaries, hitting `E` rapidly. ~3-4 emails per second.

The experienced user never looks at a list of emails. They process them one at a time, in flow, like a conveyor belt.

---

## Key Design Lessons for Sundial's Daily Outreach View

1. **Scope ruthlessly to today.** Show reps 20-30 items, not 200. Use expiration and filtering to keep the list short.
2. **One-tap reschedule is mandatory.** Date-picker reschedule has 3-4x higher abandonment than one-tap "tomorrow" or preset options.
3. **Sequential queue mode beats list-picking.** Auto-loading the next contact when one is completed is the highest-leverage UX feature for throughput.
4. **Show context inline on the list row.** Last touch, next action — visible without opening the record.
5. **Sort by engagement recency, not oldest-first.** "Oldest task first" creates a miserable experience for reps with backlog.
6. **Overdue should be a count, not a wall of shame.** Large overdue lists get ignored. Auto-expiry or bulk-clear prevents the irredeemable backlog failure mode.
7. **The completion moment matters.** When all contacts are cleared for the day, show something satisfying. Even just: "All caught up for today. Next due: Apr 10."
8. **Done → next step prompt, but fast.** After marking a contact done, immediately ask "schedule next follow-up?" with three one-tap options (1 week / 30 days / 3 months). 2 taps max.
9. **Context before action.** One line above each contact: the last extracted action item from their call. "Said closing on land end of April" tells the rep everything before they pick up the phone.

---

## Proposed Daily Outreach View Mockup

```
┌─────────────────────────────────────────────────────────────────────┐
│  Today's Outreach  ·  Apr 7                   8 due  3 overdue      │
│                                                        [▶ Start]    │
└─────────────────────────────────────────────────────────────────────┘

  OVERDUE ───────────────────────────────────────────────────────────

  🔴  Jay Eichinger · Golden Eagle                 Active · 5d overdue
      "following up on contract review"
                              [✓ Done]  [⏰ Snooze ▾]  [→ Open]

  🔴  Jeff Parmeter · Parmeter Homes               Active · 3d overdue
      "send updated floor plan options"
                              [✓ Done]  [⏰ Snooze ▾]  [→ Open]

  ─────────────────────────────────────────────────── due today

  ⚪  Sean Flaherty · Flaherty Project             Active
      "discuss timeline for spring build"
                              [✓ Done]  [⏰ Snooze ▾]  [→ Open]
```

**Snooze dropdown:**
```
  ⏰ Snooze until...
  ┌─────────────────────────┐
  │  Tomorrow               │
  │  In 3 days              │
  │  Next week              │
  │  In 30 days             │
  │  Pick a date...         │
  └─────────────────────────┘
```

**Done → next step prompt:**
```
  ✓ Marked done. Schedule next follow-up?
  [ 1 week ]  [ 30 days ]  [ 3 months ]  [ Skip ]
```

**[▶ Start]** enters queue mode — full screen, one contact at a time, auto-advances. The list is the overview. The queue is where the work happens.
