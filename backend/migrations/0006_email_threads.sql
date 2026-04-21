-- 0006_email_threads.sql
-- Stores Gmail thread metadata per client.
-- Raw message bodies are stored in messages_json for display.
-- We do not store raw email permanently in production — this is the fetch cache.

CREATE TABLE IF NOT EXISTS email_threads (
    id              TEXT PRIMARY KEY,   -- our internal ID
    client_id       TEXT NOT NULL,
    gmail_thread_id TEXT NOT NULL,      -- Google's thread ID
    subject         TEXT,
    snippet         TEXT,               -- Gmail's auto-generated preview snippet
    from_email      TEXT,               -- sender of most recent message
    participants    TEXT,               -- JSON array of all participant emails
    thread_date     TEXT NOT NULL,      -- ISO timestamp of most recent message
    message_count   INTEGER DEFAULT 1,
    messages_json   TEXT,               -- JSON array of full message objects
    fetched_at      TEXT NOT NULL,      -- when we last pulled this from Gmail
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_threads_gmail_id
    ON email_threads(client_id, gmail_thread_id);

CREATE INDEX IF NOT EXISTS idx_email_threads_date
    ON email_threads(client_id, thread_date DESC);

-- Add email_domain and contact_emails to clients table
ALTER TABLE clients ADD COLUMN email_domain   TEXT;
ALTER TABLE clients ADD COLUMN contact_emails TEXT;  -- JSON array of specific addresses
