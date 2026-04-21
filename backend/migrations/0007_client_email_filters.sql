-- 0007_client_email_filters.sql
-- Replaces email_domain + contact_emails columns on clients with a proper
-- normalized table. Each row is one filter rule: a domain or a specific address.
--
-- type = 'domain'  → match any email from/to that domain
-- type = 'address' → match a specific email address regardless of domain

CREATE TABLE IF NOT EXISTS client_email_filters (
    id         TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    type       TEXT NOT NULL CHECK(type IN ('domain', 'address')),
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, type, value)
);

CREATE INDEX IF NOT EXISTS idx_client_email_filters_client
    ON client_email_filters(client_id);

-- Migrate any existing data from the old columns
INSERT OR IGNORE INTO client_email_filters (id, client_id, type, value, created_at)
SELECT
    'cef-' || id || '-domain',
    id,
    'domain',
    email_domain,
    datetime('now')
FROM clients
WHERE email_domain IS NOT NULL AND email_domain != '';

-- Note: contact_emails is a JSON array — SQLite doesn't have json_each in all
-- versions so we leave per-address migration to a one-time manual step if needed.
-- The old columns are left in place but will no longer be read by the app.
