-- 0001_initial.sql
-- Full jobs table as it exists after phases 1–7.
-- All columns that were added via ALTER TABLE are included here
-- so a fresh DB gets the complete schema in one shot.

CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    transcript_path  TEXT NOT NULL,
    transcript_name  TEXT NOT NULL,
    project_dir      TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    started_at       TEXT,
    completed_at     TEXT,
    result           TEXT,
    error            TEXT,
    content_hash     TEXT,       -- SHA-256 of transcript text, for deduplication
    parent_job_id    TEXT,       -- set on re-run jobs
    focus_hint       TEXT,       -- optional Claude instruction for re-runs
    upload_path      TEXT,       -- path to the file in dummy_data/uploads/
    briefing         TEXT,       -- JSON blob: all briefing sections (phase-5)
    briefing_at      TEXT,       -- Pacific-time ISO when briefing was generated
    email_html       TEXT,       -- styled HTML email summary (phase-6)
    run_dir          TEXT        -- absolute path to run folder (phase-7)
);
