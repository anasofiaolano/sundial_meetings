-- 0005_oauth_states.sql
-- Ephemeral OAuth state tokens for CSRF protection.
-- Each row lives for at most 10 minutes — the cleanup runs on every callback.
-- This replaces the in-memory dict approach, which broke on server restart
-- and would fail with multiple workers sharing the same DB.

CREATE TABLE IF NOT EXISTS oauth_states (
    state      TEXT PRIMARY KEY,   -- the random token sent to Google and returned in callback
    provider   TEXT NOT NULL,      -- 'google' | 'microsoft'
    created_at TEXT NOT NULL       -- ISO timestamp — rows older than 10 min are expired
);
