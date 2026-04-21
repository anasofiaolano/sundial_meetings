# Inngest Clone — Implementation Plan

> Implementation target: `utils/inngest/`
> Replaces: `utils/inngest.py` (simple single-file queue)

---

## Why We Need the Full Model

The simple queue in `utils/inngest.py` deliberately dropped replay and step primitives because phase-1 (extract) and phase-2 (apply) were cheap enough to re-run on failure. That tradeoff no longer holds across the full product:

| Use case | Why simple queue breaks |
|---|---|
| Audio transcription before extraction | Expensive — must not repeat on retry |
| Send email / update CRM | Side effect — must fire exactly once |
| Follow-up reminders, email sequences | Need to pause execution for hours/days |
| "Did client respond within 7 days?" | Need to wait for an external event with a timeout |
| Show proposed edits, wait for approval | Job must park for hours/days, resume when consultant approves |

All five cases require step memoization, `step.sleep`, or `step.waitForEvent`. See `inngest-execution-model.md` §7 for detailed examples.

---

## File Structure

```
utils/inngest/
    __init__.py          ← public API only: Queue, NonRetriableError, JobContext
    queue.py             ← Queue class (submit, send_event, get_jobs, start, stop)
    worker.py            ← worker loop + replay engine
    step.py              ← StepContext (step.run, step.sleep, step.wait_for_event)
    signals.py           ← internal BaseException signals (_StepCompleted, _SleepUntil, _WaitForEvent)
    state.py             ← JobRecord dataclass + StateBackend abstract base
    scheduler.py         ← tick loop: wake sleeping jobs, expire timed-out waits
    logging.py           ← shared logger setup
    backends/
        __init__.py      ← re-exports + make_backend_from_env()
        memory.py        ← in-process dict (tests, CI)
        sqlite.py        ← SQLite on disk (Fly.io default)
        postgres.py      ← PostgreSQL (AWS multi-instance)
```

Every public symbol the caller ever touches is exported from `__init__.py`. Nothing else is imported directly from callers.

---

## Public API

### Constructor

```python
Queue(
    handler:       Callable[[JobContext], Awaitable[Any]],
    backend:       StateBackend | None = None,   # default: SqliteBackend via make_backend_from_env()
    max_attempts:  int = 3,
    backoff_secs:  list[int] | None = None,      # default: [15, 30, 60, 120]
    concurrency:   int = 1,
)
```

`backend=None` calls `make_backend_from_env()` which reads `INNGEST_BACKEND` env var:
- `sqlite` (default) → `SqliteBackend(os.environ.get("INNGEST_DB_PATH", "jobs.db"))`
- `postgres` → `PostgresBackend(os.environ["DATABASE_URL"])`
- `memory` → `MemoryBackend()`

### Submit

```python
job: JobRecord = await queue.submit(**payload)
```

Same call signature as today. Returns a `JobRecord` dataclass.

### Send event (new)

```python
resumed_ids: list[str] = await queue.send_event(event_name: str, data: dict)
```

Resumes every job parked in `status="waiting"` whose `waiting_for.event == event_name`.
Called from a FastAPI route when a webhook fires or a user clicks "Approve".

### Queries

```python
queue.get_jobs() -> list[JobRecord]
queue.get_job(job_id) -> JobRecord | None
```

### Lifecycle

```python
await queue.start()   # load state, re-queue unfinished jobs, start worker + scheduler
await queue.stop()    # cancel both tasks gracefully
```

### Handler signature

```python
async def my_handler(ctx: JobContext) -> Any:
    result = await ctx.step.run("step-id", my_async_fn)
    await ctx.step.sleep("wait-1", timedelta(hours=24))
    event = await ctx.step.wait_for_event("approval", "edits.approved", timeout=timedelta(days=7))
    ...
```

`ctx.payload` is the original submit kwargs. `ctx.job` is the full `JobRecord`. `ctx.step` is the step helper.

Handlers that never call `ctx.step` work identically to today — no overhead.

---

## Internal Architecture

### Step signals (`signals.py`)

Three internal exceptions carry control flow. They derive from `BaseException` — not `Exception` — so they cannot be swallowed by a bare `except Exception` block inside a handler.

```python
class _StepCompleted(BaseException):
    step_id: str
    result:  Any

class _SleepUntil(BaseException):
    step_id:   str
    resume_at: datetime

class _WaitForEvent(BaseException):
    step_id:    str
    event:      str
    timeout_at: datetime
```

### StepContext (`step.py`)

Constructed fresh for each replay iteration. Receives the current memo map for the job.

**`step.run(id, fn)`**
1. `id in memo` → return `memo[id]` immediately (replay fast-path, no work done)
2. else → `result = await fn()` → raise `_StepCompleted(id, result)`

**`step.sleep(id, duration)`**
1. `id in memo` → return immediately (already slept on a prior execution)
2. else → raise `_SleepUntil(id, now() + duration)`

**`step.wait_for_event(id, event, timeout)`**
1. `id in memo` → return `memo[id]` (event payload, or `None` if timed out)
2. else → raise `_WaitForEvent(id, event, now() + timeout)`

### Worker replay loop (`worker.py`)

```
Dequeue job_id
Load JobRecord from backend
Build StepContext(memo=job.steps)
Call handler(ctx)

  ┌─ Returns normally ──────────────────────────────────── status → "done", result saved
  │
  ├─ _StepCompleted(step_id, result) ──────────────────── save memo[step_id] = result
  │                                                        append step_id to stack
  │                                                        re-enqueue job_id (replay from top)
  │
  ├─ _SleepUntil(step_id, resume_at) ──────────────────── save memo[step_id] = "__sleeping__"
  │                                                        status → "sleeping", sleep_until = resume_at
  │                                                        do NOT re-enqueue (scheduler handles wake-up)
  │
  ├─ _WaitForEvent(step_id, event, timeout_at) ────────── save memo[step_id] = "__waiting__"
  │                                                        status → "waiting", waiting_for = {event, timeout_at}
  │                                                        do NOT re-enqueue (send_event() or tick handles resume)
  │
  ├─ NonRetriableError ────────────────────────────────── status → "failed", no retry
  │
  └─ Any other Exception ──────────────────────────────── attempt += 1
                                                          if attempt >= max_attempts → "failed"
                                                          else → re-enqueue after backoff delay
```

On resume (sleep wake-up or event received), the memo entry is updated from the sentinel to the real value before re-enqueueing. The handler replays from top; completed steps skip instantly; the previously-parked step now returns its value; execution continues forward.

### JobRecord (`state.py`)

```python
@dataclass
class JobRecord:
    id:           str
    status:       Literal["queued", "running", "sleeping", "waiting", "done", "failed"]
    payload:      dict
    attempt:      int
    max_attempts: int
    steps:        dict[str, Any]      # memo map: step_id → output
    stack:        list[str]           # ordered list of completed step IDs
    sleep_until:  datetime | None
    waiting_for:  dict | None         # {"event": str, "timeout_at": str ISO}
    result:       Any
    error:        str | None
    created_at:   datetime
    updated_at:   datetime
```

`steps` and `waiting_for` are stored as JSON columns. Everything else is a native column.

### Scheduler (`scheduler.py`)

Runs as a second asyncio task alongside the worker. Every 10 seconds (configurable):

1. **Wake sleeping jobs**: `backend.load_sleeping_jobs(before=now())` → update memo, status → "queued", re-enqueue
2. **Expire timed-out waits**: `backend.load_timed_out_waiting_jobs(before=now())` → set memo to `None`, status → "queued", re-enqueue

The tick interval means sleep granularity is ~10 seconds — fine for hour/day-scale waits.

---

## State Backend Options

### `MemoryBackend` — tests and CI

In-process dict. Jobs lost on exit. Zero setup. Use in unit tests and CI.

### `SqliteBackend` — default, Fly.io

Single `.db` file using WAL mode. Survives restarts. Zero external services.

**For Fly.io:** Mount a persistent volume at `/data`, set `INNGEST_DB_PATH=/data/jobs.db`. Single instance, no locking issues.

### `PostgresBackend` — AWS multi-instance

`psycopg2` (sync, wrapped in `asyncio.to_thread`). Uses `SELECT ... FOR UPDATE SKIP LOCKED` on dequeue to safely share jobs across multiple workers on multiple machines.

**For AWS:** ECS/Fargate with RDS Postgres. Set `INNGEST_BACKEND=postgres`, `DATABASE_URL=postgresql://...`.

Switching backend requires changing one env var. No handler code changes.

---

## Simple Handlers Have Zero Overhead

A handler that never calls `ctx.step`:

```python
async def my_handler(ctx: JobContext) -> dict:
    result = do_work(ctx.payload)
    return result
```

The worker calls it, gets a return value, no signal raised → job done. The memo map is `{}` throughout. The replay loop never fires. Identical behavior to `utils/inngest.py` today.

---

## Migration from `utils/inngest.py`

### Step 1 — Create the package

`utils/inngest/` directory with `__init__.py`. Python resolves package directories before `.py` files — once the directory exists, `from inngest import Queue` imports from the package. Old file deleted after testing.

### Step 2 — Backward-compatible constructor

`Queue(jobs_file=..., handler=...)` still accepted. `jobs_file` maps to `SqliteBackend(path)` internally (deprecated parameter, kept for one release cycle). `phase-3/server.py` constructor call unchanged.

### Step 3 — Handler signature

```python
# Before
async def handle_transcript(job: dict) -> dict:
    payload = job["payload"]

# After
async def handle_transcript(ctx: JobContext) -> dict:
    payload = ctx.payload
```

Only required change. `NonRetriableError` raise syntax identical.

### Step 4 — Add steps where needed

Wrap expensive or side-effectful calls in `ctx.step.run(...)`. Handlers that don't need it remain as-is.

---

## Implementation Sequence

**Phase 1 — Core (no behavioral change)**
`signals.py`, `state.py`, `backends/memory.py`, `backends/sqlite.py`, `step.py` (run only), `worker.py` (cases A, B, E, F), `queue.py`, `__init__.py`.
SQLite replaces `jobs.json`. Simple handler path works. Migrate `phase-3/server.py`.

**Phase 2 — `step.sleep`**
`_SleepUntil` in worker, `scheduler.py` (sleeping wake-up), `step.sleep` in StepContext.
Enables: email sequences, reminders.

**Phase 3 — `step.waitForEvent`**
`_WaitForEvent` in worker, `send_event()` on Queue, timeout handling in scheduler, `step.wait_for_event` in StepContext.
Enables: human-in-the-loop approval, client-response timeout.

**Phase 4 — PostgresBackend** ← implement at or before first staging deploy
SQLite is single-process only — not safe on stateless cloud deployments.
`backends/postgres.py`, `make_backend_from_env()`. No changes to Queue, worker, or any handler.

Fly.io:  `fly postgres create` → set `DATABASE_URL` secret → `INNGEST_BACKEND=postgres`
AWS:     RDS Postgres (db.t3.micro to start) → same env vars

Enables: Fly/AWS staging and production, multi-instance horizontal scaling.

---

## Key Design Decisions

**`BaseException` for signals, not `Exception`.**
Handler code may have broad `except Exception` blocks. If signals derived from `Exception`, a catch-all would swallow them silently — the worker would treat a mid-flight step as job completion. `BaseException` makes signals invisible to user-space handlers.

**Synchronous `StateBackend`.**
SQLite reads are microseconds. No async overhead needed. If PostgreSQL async is required, wrap in `asyncio.to_thread`. Simpler interface, simpler worker.

**Memo map in the same row as the job, not a separate table.**
Always read and written together. Single-row access is simpler and faster than a join. Memo maps are small (a few KB per job at most).

**Sentinel values in the memo (`"__sleeping__"`, `"__waiting__"`).**
The step_id must appear in the memo so replay skips it. But the result is meaningless. A sentinel string is cleaner than `None` (valid result) and avoids a separate boolean flag per step.

**Tick-based scheduler, not per-job timers.**
Per-job `asyncio.Task` timers would need to be recreated on restart (state to recover) and cancelled on job failure (bookkeeping). A tick loop is stateless — it just queries the backend for overdue jobs.

**Single worker by default.**
`apply_edits.py` has a module-level `read_file_state` dict. Concurrent workers on the same `project_dir` would race on reads and writes. Default `concurrency=1` avoids this. Increasing concurrency requires either moving `read_file_state` to a per-call scope or scoping workers by project.
