# Inngest Execution Model — Technical Reference

> Source: read from `/utils/reference/inngest-main` (Go monorepo)

---

## The Core Idea

Inngest achieves durability through **deterministic replay with memoization**. A function is a stateless generator that gets re-executed from the top on every step. Completed steps are skipped by checking a memo map. This means:

- The function runs from scratch each time a new step needs to execute
- Already-completed steps return their cached output instantly
- If the server crashes mid-step, the function just replays again from the top — no work is lost

---

## 1. The Replay / Memoization Model

### State per run

`/pkg/execution/state/v2/state.go`

```go
type State struct {
    Metadata Metadata
    Events   []json.RawMessage
    Steps    map[string]json.RawMessage  // stepID → output
}
```

The `Stack` inside `Metadata` is an **ordered list of completed step IDs**. It's the source of truth for what has already been done.

### How replay works

When the server needs to continue a run (new step, retry, resume from sleep):

1. Load all memoized step outputs from the state store
2. Build a request payload containing:
   - The triggering events
   - `actions` map: stepID → output for every completed step
   - `stack`: ordered list of completed step IDs
3. POST this to the SDK endpoint
4. SDK re-executes the function from line 1
5. Every `step.run("id", fn)` call checks: "is this ID in `actions`?"
   - **Yes** → return cached output immediately, keep going
   - **No** → actually execute `fn`, return a `206 Partial Content` with an opcode
6. Server receives the opcode, saves the output, re-enters the function

The function replays until it hits a step that hasn't run yet, then pauses there.

### Step IDs

Each step is identified by a hash of its **name + position in code**. Same step = same ID across all runs and retries. This makes the memo lookup deterministic.

### What gets stored

`/pkg/execution/state/redis_state/redis_state.go`

Step outputs are wrapped before storage:
- Success: `{"data": <output>}`
- Error: `{"error": <UserError>}`

This wrapping tells the SDK whether to return the value or throw on replay.

Storage is atomic via Lua scripts — step output and stack append happen in one transaction.

---

## 2. The Step Execution Protocol (206 vs 200)

`/pkg/execution/driver/httpdriver/httpdriver.go`
`/pkg/execution/state/opcode.go`

The server POSTs to the SDK endpoint. The response signals what happens next:

| Status | Meaning |
|--------|---------|
| `200 OK` | Function finished. Body is the final return value. |
| `206 Partial Content` | Function paused at a step. Body contains **GeneratorOpcodes**. |
| `4xx / 5xx` | Error — retry logic kicks in. |

### GeneratorOpcode

```go
type GeneratorOpcode struct {
    Op    enums.Opcode        // what the SDK wants to do
    ID    string              // step ID (hashed)
    Name  string              // human-readable step name
    Data  json.RawMessage     // step output (if success)
    Error *UserError          // error details (if failure)
}
```

### Opcode types

| Opcode | Meaning |
|--------|---------|
| `OpcodeStepRun` | Step completed successfully. Save output, continue. |
| `OpcodeStepError` | Step failed. Check retries. |
| `OpcodeStepFailed` | Final failure (no more retries). |
| `OpcodeSleep` | Pause until a timestamp. Enqueue a wake-up job. |
| `OpcodeWaitForEvent` | Pause until a matching event arrives. |
| `OpcodeRunComplete` | Function is done. Finalize the run. |

---

## 3. Queue Mechanics

`/pkg/execution/queue/item.go`
`/pkg/execution/queue/process.go`

### QueueItem

```go
type QueueItem struct {
    ID          string     // idempotency key (hashed)
    AtMS        int64      // when to execute (Unix ms)
    Attempt     int        // zero-indexed retry counter
    MaxAttempts *int       // cap (default: 4 = 3 retries + first attempt)
    LeaseID     *ulid.ULID // prevents concurrent processing
    Data        Item       // job payload
}
```

### Job kinds

| Kind | When it's enqueued |
|------|--------------------|
| `KindStart` | Event matches a function trigger |
| `KindEdge` | A step completed and the next needs to run |
| `KindSleep` | Function called `step.sleep()` |
| `KindPause` | Function called `step.waitForEvent()` |
| `KindEdgeError` | Step permanently failed, error handlers fire |

### Priority

Older runs get priority. The queue score is:

```go
score = run_start_timestamp - priority_factor
```

Lower score = runs first. This prevents new high-volume runs from starving old ones.

### Processing loop

1. Dequeue item → acquire a **lease** (ULID with expiration)
2. Extend the lease periodically while job runs
3. Call the executor
4. On success: release lease, job is done
5. On failure: check `ShouldRetry()` → requeue with backoff or mark failed

---

## 4. Retry Logic

`/pkg/execution/queue/process.go`
`/pkg/backoff/backoff.go`

### Decision

```go
func ShouldRetry(err error, attempt int, maxAttempts int) bool {
    if attempt >= maxAttempts  { return false }
    if IsNeverRetryable(err)   { return false }
    return true
}
```

`NonRetriableError` (what the SDK exposes as `inngest.NonRetriableError`) sets `NeverRetryable = true`.

### Backoff table

```go
var BackoffTable = []time.Duration{
    15 * time.Second,  // attempt 0
    30 * time.Second,  // attempt 1
    1  * time.Minute,  // attempt 2
    2  * time.Minute,  // attempt 3
    5  * time.Minute,  // attempt 4
    10 * time.Minute,  // attempt 5
    20 * time.Minute,  // attempt 6
    40 * time.Minute,  // attempt 7
    1  * time.Hour,    // attempt 8
    2  * time.Hour,    // attempt 9+
}
```

Each delay gets +0–30s random jitter.

Custom retry time: if the error implements `RetryAtSpecifier`, that timestamp is used instead of the table.

### Attempt counter

`Attempt` lives on the `QueueItem`. On each retry:
- `Attempt += 1`
- Item is re-enqueued with new `AtMS`
- Same `RunID` — the retry continues the same run

---

## 5. Full Lifecycle

```
Event arrives
  └─ Match against function triggers
       └─ Schedule() called
            ├─ Generate RunID (ULID)
            ├─ Initialize state: Stack=[], Steps={}
            ├─ Store triggering events
            └─ Enqueue KindStart item (AtMS = now)

Queue processor dequeues KindStart
  └─ Execute()
       ├─ Load metadata + function definition
       ├─ Marshal request (events + empty steps + empty stack)
       └─ POST to SDK endpoint

SDK responds 206 with OpcodeStepRun
  └─ HandleGenerator()
       ├─ Save step output to state → Stack = ["step-1"]
       └─ Enqueue KindEdge to continue

Queue processor dequeues KindEdge
  └─ Execute()
       ├─ Load state: Steps = {"step-1": {...}}, Stack = ["step-1"]
       ├─ Marshal request (events + memoized step-1 + stack)
       └─ POST to SDK endpoint

SDK replays:
  - hits step-1 → finds it in actions map → returns cached output instantly
  - hits step-2 → not in actions map → executes it → returns 206

  ... (repeat for each step)

SDK responds 200 with final output
  └─ Finalize()
       ├─ Mark run complete
       ├─ Delete state from store
       └─ Emit function.finished event
```

### On failure

```
SDK responds 5xx or step throws
  └─ ShouldRetry(attempt, maxAttempts)?
       ├─ YES → Requeue with backoff, Attempt += 1
       │         On next execution: replay all completed steps,
       │         re-execute only the failed step
       └─ NO  → OpcodeStepFailed → Finalize as failed
                 Emit function.failed event
```

---

## 6. Our Python Implementation — What We Kept and Dropped

Implementation lives in `utils/inngest.py` (generic queue engine) and `phase-3/server.py` (wires it to phase-1 + phase-2).

### Kept

| Inngest concept | Our equivalent | Notes |
|----------------|----------------|-------|
| State store (Redis) | `jobs.json` on disk | Atomic write via `.tmp` + rename. Loaded on startup. |
| Queue (Redis sorted set) | `asyncio.Queue` | In-memory. Re-populated from `jobs.json` on restart. |
| Attempt counter | `job["attempt"]` | Incremented on each failure before re-queue. |
| Backoff table | `[5s, 30s, 120s]` | Simplified from 10-entry table (15s→2h). Short jobs don't need hour-scale waits. |
| `NonRetriableError` | `NonRetriableError` (same name) | Raised in handler to fail immediately. E.g. transcript file missing. |
| Crash recovery | Re-queue on startup | Any job with `status == "running"` or `"queued"` at startup is re-enqueued. Equivalent to Inngest re-processing lease-expired items. |
| `on_failure` | `status = "failed"`, `error = str(e)` | Persisted to `jobs.json`. |

### Dropped

| Inngest feature | Why we dropped it |
|----------------|-------------------|
| **Replay / memoization** | Inngest re-executes the whole function from scratch on every step, using a memo map to skip completed steps. We don't need this — if a job fails, we restart from phase-1. Extract + apply are fast and cheap enough to re-run. |
| **206 Partial Content opcode protocol** | Only needed for the replay model. We call phase-1 and phase-2 as plain Python functions, no HTTP boundary between steps. |
| **`step.run` / `step.sleep` / `step.waitForEvent`** | These primitives exist to checkpoint individual steps for replay. Without replay, they have no purpose. Our handler is just a plain `async def`. |
| **Concurrent workers + lease IDs** | `apply_edits.py` uses a module-level `read_file_state` dict. Concurrent workers on the same `project_dir` would race. One worker = no locking needed. |
| **Redis** | No external dependencies. `asyncio.Queue` + `jobs.json` is sufficient for single-machine use. |
| **Priority scoring** (`score = run_start - priority_factor`) | We process jobs FIFO. No starvation risk at our scale. |

### Architecture

```
utils/inngest.py          — generic engine: Queue class, NonRetriableError, retry, persistence
phase-3/server.py         — application layer: defines handle_transcript(), mounts API
phase-3/jobs.json         — persisted job state (created at runtime)
```

`utils/inngest.py` knows nothing about transcripts or phases. `phase-3/server.py` is what gives it meaning — it defines the handler that runs phase-1 → phase-2 and passes it to the `Queue` constructor.

---

## 7. When the Full Model Is Required

The simplified queue above (no replay, no step primitives) is sufficient for the current phase-1 → phase-2 pipeline because both steps are cheap and idempotent. But the following real use cases in this product require the full model.

### Case 1 — Expensive steps that must not repeat on failure

**Example:** Transcribing audio files before extraction.

Audio transcription is slow and potentially expensive. If transcription succeeds but extraction fails, replaying from scratch means paying for transcription again. With `step.run` memoization, the transcription output is saved to the job's state store after the first successful call — on any subsequent retry, it's returned from cache instantly.

```python
transcript = await ctx.step.run("transcribe", lambda: transcribe_audio(audio_path))
edits      = await ctx.step.run("extract",    lambda: extract(transcript, project_dir))
```

If extraction fails and the job retries, `transcribe` is skipped. Only `extract` re-runs.

---

### Case 2 — Side effects that must fire exactly once

**Examples:** Sending a follow-up email, creating or updating a CRM record, posting to Slack.

Without memoization, a crash between step 2 and step 3 causes the entire handler to re-run on retry — including step 1's email send or CRM write. The client gets two emails. The CRM gets a duplicate record. Wrapping side effects in `step.run` records their completion in the memo map, so they are skipped on replay.

```python
await ctx.step.run("update-crm",  lambda: crm.update_contact(contact_id, notes))
await ctx.step.run("send-email",  lambda: email.send(client_email, "Here's your summary..."))
```

---

### Case 3 — Long waits between steps (`step.sleep`)

**Examples:** Setting a follow-up reminder 3 days after a meeting. Enrolling a contact in an email sequence with timed delays (day 1, day 4, day 10).

`step.sleep` pauses the function at a specific point in execution for a given duration without holding a thread or process open. The job is parked (status = `"sleeping"`, `sleep_until` stored), and a background tick wakes it up when the time arrives. Execution resumes from exactly where it paused — all prior steps are already memoized.

```python
await ctx.step.run("send-day-1-email",  lambda: email.send(client, day1_content))
await ctx.step.sleep("wait-day-4",      timedelta(days=3))
await ctx.step.run("send-day-4-email",  lambda: email.send(client, day4_content))
await ctx.step.sleep("wait-day-10",     timedelta(days=6))
await ctx.step.run("send-day-10-email", lambda: email.send(client, day10_content))
```

---

### Case 4 — Waiting for an external event with a timeout (`step.waitForEvent`)

**Example:** After sending a proposal, pause until the client responds — but if they haven't responded in 7 days, take a different action.

`step.waitForEvent` parks the job (status = `"waiting"`) and stores what event it's waiting for and when it times out. When `queue.send_event(event_name, data)` is called (e.g. from a webhook), any matching parked job is resumed with the event data. If the timeout expires first, the job resumes with `None` and can branch accordingly.

```python
response = await ctx.step.wait_for_event(
    "client-response",
    event="proposal.responded",
    timeout=timedelta(days=7),
)

if response is None:
    await ctx.step.run("send-nudge", lambda: email.send(client, nudge_content))
else:
    await ctx.step.run("log-response", lambda: crm.log(response))
```

---

### Case 5 — Human-in-the-loop approval before applying changes

**Example:** After extraction (phase-1), show the consultant the proposed edits in the UI. Wait for them to review and approve. Only then run phase-2 to write to disk.

This combines `step.run` memoization (extraction is saved — re-opening the job doesn't re-call Claude) with `step.waitForEvent` (the job parks until the UI fires an `"edits.approved"` event, which could be hours or days later). The approval payload from the UI is passed directly into phase-2, so the consultant's selections are honored.

```python
edits = await ctx.step.run("extract", lambda: extract(transcript, project_dir))

# Job parks here. UI shows diffs. Consultant reviews.
approval = await ctx.step.wait_for_event(
    "await-approval",
    event="edits.approved",
    timeout=timedelta(days=30),
)

if approval is None:
    return {"status": "expired", "reason": "no approval within 30 days"}

result = await ctx.step.run("apply", lambda: apply_batch(approval["edits"], project_dir, ...))
await ctx.step.run("notify", lambda: email.send(consultant_email, "Edits applied.", result))
```

---

### Revised architecture for full model

```
Job state (per job in jobs.json):
  steps:        dict[step_id, output]        ← memo map (what Inngest stores in Redis)
  stack:        list[step_id]                ← order of completed steps
  status:       queued | running | sleeping | waiting | done | failed
  sleep_until:  ISO datetime | null
  waiting_for:  { event, timeout_at } | null

Step signals (Python exceptions, internal to utils/inngest.py):
  _StepCompleted(step_id, result)            → save to memo, re-execute handler from top
  _SleepUntil(step_id, resume_at)            → park job, schedule tick wake-up
  _WaitForEvent(step_id, event, timeout_at)  → park job, resume on send_event()

New public methods on Queue:
  queue.send_event(event_name, data)         → resume any job waiting for that event
  queue.tick()                               → wake up jobs whose sleep_until has passed
```
