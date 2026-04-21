-- 0008_gmail_sync_state.sql
-- Stores per-client Gmail sync cursors for incremental sync via the History API.
--
-- Why per-client (not per-account): one Google account can serve multiple clients,
-- each with different email filter sets. The historyId is mailbox-wide but the
-- filtered thread set is per-client, so each client needs its own cursor.
--
-- history_id: the Gmail historyId cursor from the last successful sync.
--             Passed as startHistoryId on the next incremental sync.
--             On HTTP 404 (cursor expired, ~1 week TTL), we do a full resync
--             and write a fresh cursor.
--
-- last_full_sync: timestamp of the last complete resync (not just incremental).
--                 We do a full resync periodically as a safety net because Gmail's
--                 messagesAdded history entries occasionally miss messages (known bug).

CREATE TABLE IF NOT EXISTS gmail_sync_state (
    client_id      TEXT PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    account_id     TEXT NOT NULL REFERENCES email_accounts(id) ON DELETE CASCADE,
    history_id     TEXT NOT NULL,
    last_full_sync TEXT,
    last_synced_at TEXT NOT NULL
);
