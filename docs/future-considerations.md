# Future Considerations

Running notes on architectural trade-offs, known limitations, and things to revisit as the system grows.

---

## In-process queue vs. real Inngest (or external queue)

Our queue (`utils/inngest/`) runs entirely inside the FastAPI process — the worker and scheduler are asyncio background tasks, not separate services. This is the right call for now but has real limits.

**Pros of our approach:**
- Zero infrastructure — one `uvicorn` command and it works
- Simple to reason about — everything is in one process, one codebase
- SQLite persistence means jobs survive server restarts
- No network hop between queue server and worker — lower latency, no auth needed
- Easier to debug — single log stream, single process to inspect

**Cons vs. real Inngest (or any out-of-process queue):**
- **Single point of failure** — if the process dies mid-job, the job is interrupted. Crash recovery on startup handles most of this, but there's a window.
- **No horizontal scaling** — you can't run multiple instances picking up from the same queue. SQLite is single-file, single-process. Switching to `PostgresBackend` (already stubbed in `utils/inngest/backends/postgres.py`) would fix this.
- **Worker and web server share the same process** — a CPU-heavy job (long Claude call) will slow down HTTP responses. Real Inngest separates these.
- **No dashboard** — real Inngest gives you a UI showing job history, step traces, retries. We have `/api/jobs` but that's it.
- **No fan-out / parallel steps** — real Inngest can run multiple steps concurrently. Our worker is concurrency=1 by design (the `read_file_state` issue in `apply_edits.py` — see Phase 5 TODO).
- **No rate limiting or throttling primitives** — Inngest has built-in concurrency controls, rate limits, debounce. We have none.
- **No cron/scheduled jobs** — Inngest has first-class cron support. We'd have to build that separately.

**The line:** For a single-server app on Fly.io processing a few transcripts a day, the in-process approach is completely fine and far simpler. The moment you need multiple workers, a real dashboard, or high throughput — switch to PostgresBackend + separate worker process, or adopt real Inngest/BullMQ/Celery.
