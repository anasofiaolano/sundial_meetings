-- 0009_call_sessions.sql
-- Live call notetaking sessions and individual notes.
-- Sessions are created when "Start call" is clicked and ended when the call
-- wraps up. Notes are the bullets typed during the session.
-- After the call, uploading the transcript links session.job_id so the
-- briefing pipeline can use your notes as emphasis signals (Granola model).

CREATE TABLE IF NOT EXISTS call_sessions (
    id          TEXT PRIMARY KEY,
    client_id   TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    job_id      TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'ended')),
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS call_notes (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES call_sessions(id) ON DELETE CASCADE,
    text        TEXT NOT NULL DEFAULT '',
    type        TEXT NOT NULL DEFAULT 'note'
                    CHECK(type IN ('note', 'action', 'question', 'commitment', 'private')),
    is_bookmark INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_call_sessions_client ON call_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_call_notes_session   ON call_notes(session_id, position);
