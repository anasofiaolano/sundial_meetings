-- 0003_chat_threads.sql
-- Chat history persistence: threads (conversations) + messages

CREATE TABLE IF NOT EXISTS chat_threads (
    id         TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT 'New conversation',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_client ON chat_threads(client_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id            TEXT PRIMARY KEY,
    thread_id     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content       TEXT NOT NULL,
    context_items TEXT,   -- JSON array of {type, id/rel} — stored for display only
    usage         TEXT,   -- JSON {input_tokens, output_tokens, cost_usd, cost_str}
    created_at    TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id, created_at);
