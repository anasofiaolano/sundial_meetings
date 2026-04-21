# utils/inngest.py — Inngest-inspired job queue
#
# A simplified port of Inngest's execution model to Python/asyncio.
# See docs/inngest-execution-model.md for the full reference.
#
# What we kept from Inngest:
#   - Job persistence (jobs.json ≈ Redis state store)
#   - Crash recovery: re-queue stuck/pending jobs on startup
#   - Attempt counter + backoff
#   - NonRetriableError for skipping retries
#   - Single-worker sequential processing (no lease IDs needed)
#
# What we dropped:
#   - Replay/memoization (our steps are idempotent; restart is fine)
#   - 206 opcode protocol (we call Python directly, no HTTP boundary)
#   - step.run / step.sleep / step.waitForEvent primitives
#   - Redis (asyncio.Queue + jobs.json covers our scale)
#   - Concurrent workers (avoids read_file_state race in apply_edits)
#
# Usage:
#   async def my_handler(job: dict) -> dict:
#       # do work; raise NonRetriableError to fail without retry
#       return {"result": "..."}
#
#   queue = Queue(jobs_file=Path("jobs.json"), handler=my_handler)
#   await queue.start()
#   job = await queue.submit(transcript_path="...", transcript_name="...")
#   await queue.stop()

import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Module-level logger (callers can configure their own handlers on top)
# ---------------------------------------------------------------------------
_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_handler_file = RotatingFileHandler(
    _LOG_DIR / "inngest.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_handler_file.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)-8s [inngest] — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

log = logging.getLogger("inngest")
log.setLevel(logging.DEBUG)
if not log.handlers:
    log.addHandler(_handler_file)
    log.addHandler(logging.StreamHandler(sys.stderr))


# ---------------------------------------------------------------------------
# NonRetriableError
# Raise inside a handler to fail the job immediately without retrying.
# Equivalent to inngest.NonRetriableError / sdk-go NeverRetryable.
# ---------------------------------------------------------------------------
class NonRetriableError(Exception):
    """Fail this job immediately. No further retry attempts will be made."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short(job_id: str) -> str:
    return job_id[:8]


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------
class Queue:
    """
    asyncio.Queue-backed job queue with persistence, retry, and crash recovery.

    Parameters
    ----------
    jobs_file : Path
        Where to persist job state (written atomically on every status change).
    handler : async callable
        async def handler(job: dict) -> dict
        Receives the full job dict. Return value is stored as job["result"].
        Raise NonRetriableError to fail without retry.
        Raise any other exception to trigger retry with backoff.
    max_attempts : int
        Total attempts before a job is marked failed (default 3).
    backoff_secs : list[int]
        Delay in seconds before each retry attempt. Index = attempt number - 1.
        Defaults to [5, 30, 120].
    """

    def __init__(
        self,
        jobs_file: Path,
        handler: Callable,
        max_attempts: int = 3,
        backoff_secs: list[int] | None = None,
    ):
        self.jobs_file    = jobs_file
        self.handler      = handler
        self.max_attempts = max_attempts
        self.backoff_secs = backoff_secs or [5, 30, 120]

        self._jobs: dict[str, dict] = {}
        self._queue: asyncio.Queue | None = None
        self._worker_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save(self):
        try:
            tmp = self.jobs_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(list(self._jobs.values()), indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.jobs_file)
        except Exception:
            log.exception("_save FAILED")

    def _load(self):
        if not self.jobs_file.exists():
            return
        try:
            data = json.loads(self.jobs_file.read_text(encoding="utf-8"))
            for job in data:
                self._jobs[job["id"]] = job
            log.info("loaded %d job(s) from %s", len(self._jobs), self.jobs_file)
        except Exception:
            log.exception("_load FAILED — starting with empty jobs store")

    def _update(self, job_id: str, **kwargs):
        if job_id not in self._jobs:
            return
        self._jobs[job_id].update(kwargs)
        self._jobs[job_id]["updated_at"] = _now()
        self._save()

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------
    def get_jobs(self) -> list[dict]:
        """Return all jobs sorted newest first."""
        return sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)

    def get_job(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------
    async def submit(self, **payload) -> dict:
        """
        Create a new job and enqueue it.

        All keyword arguments are stored as job["payload"] and passed to the handler.
        Returns the new job dict.
        """
        job = {
            "id":           str(uuid.uuid4()),
            "status":       "queued",   # queued | running | done | failed
            "payload":      payload,
            "attempt":      0,
            "max_attempts": self.max_attempts,
            "created_at":   _now(),
            "updated_at":   _now(),
            "result":       None,       # set on done: handler return value
            "error":        None,       # set on failed: exception message
        }
        self._jobs[job["id"]] = job
        self._save()
        await self._queue.put(job["id"])
        log.info("submitted job %s — payload keys: %s", _short(job["id"]), list(payload.keys()))
        return job

    # ------------------------------------------------------------------
    # Retry scheduling
    # ------------------------------------------------------------------
    async def _schedule_retry(self, job_id: str, delay: float):
        log.info("job %s retrying in %.0fs", _short(job_id), delay)
        await asyncio.sleep(delay)
        await self._queue.put(job_id)
        log.info("job %s re-queued", _short(job_id))

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------
    async def _worker(self):
        log.info("worker started")
        while True:
            job_id = await self._queue.get()
            try:
                job = self._jobs.get(job_id)
                if not job:
                    log.warning("worker: unknown job %s — skipping", _short(job_id))
                    continue

                log.info("running job %s (attempt %d/%d)",
                         _short(job_id), job["attempt"] + 1, job["max_attempts"])
                self._update(job_id, status="running")

                try:
                    result = await self.handler(job)
                    self._update(job_id, status="done", result=result)
                    log.info("job %s done", _short(job_id))

                except NonRetriableError as e:
                    log.error("job %s NonRetriableError — failing immediately: %s", _short(job_id), e)
                    self._update(job_id, status="failed", error=f"NonRetriableError: {e}")

                except Exception as e:
                    attempt = job["attempt"] + 1
                    self._update(job_id, attempt=attempt)
                    job = self._jobs[job_id]  # re-fetch

                    if attempt >= job["max_attempts"]:
                        log.error("job %s FAILED after %d attempt(s): %s",
                                  _short(job_id), attempt, e)
                        self._update(job_id, status="failed", error=str(e))
                    else:
                        delay = self.backoff_secs[min(attempt - 1, len(self.backoff_secs) - 1)]
                        log.warning("job %s attempt %d failed — retry in %ds: %s",
                                    _short(job_id), attempt, delay, e)
                        self._update(job_id, status="queued")
                        asyncio.create_task(self._schedule_retry(job_id, delay))

            finally:
                self._queue.task_done()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self):
        """Load persisted state, re-queue unfinished jobs, start the worker."""
        self._load()
        self._queue = asyncio.Queue()

        # Crash recovery: any job stuck in "running" or still "queued" gets re-enqueued.
        # Equivalent to Inngest re-processing lease-expired items on startup.
        requeued = 0
        for job in self._jobs.values():
            if job["status"] in ("running", "queued"):
                if job["status"] == "running":
                    log.warning("re-queuing stuck job %s (was running at shutdown)",
                                _short(job["id"]))
                    self._update(job["id"], status="queued")
                await self._queue.put(job["id"])
                requeued += 1

        self._worker_task = asyncio.create_task(self._worker())
        log.info("queue started — %d pending job(s)", requeued)

    async def stop(self):
        """Cancel the worker task gracefully."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        log.info("queue stopped")
