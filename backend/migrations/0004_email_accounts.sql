-- 0004_email_accounts.sql
-- Connected email accounts (Gmail, Outlook) with OAuth tokens

CREATE TABLE IF NOT EXISTS email_accounts (
    id            TEXT PRIMARY KEY,
    provider      TEXT NOT NULL CHECK(provider IN ('google', 'microsoft')),
    email_address TEXT NOT NULL,
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry  TEXT NOT NULL,   -- ISO 8601 UTC timestamp
    scopes        TEXT,            -- space-separated scopes actually granted
    status        TEXT NOT NULL DEFAULT 'active'
                       CHECK(status IN ('active', 'broken')),
                       -- 'broken' = refresh failed, user needs to reconnect
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_accounts_provider_email
    ON email_accounts(provider, email_address);
