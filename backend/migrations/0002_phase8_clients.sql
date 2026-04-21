-- 0002_phase8_clients.sql
-- Introduces multi-client CRM layer (phase-8).
-- Adds: groups, clients, files tables + client_id on jobs.

ALTER TABLE jobs ADD COLUMN client_id TEXT;  -- FK → clients.id

CREATE TABLE groups (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    position   INTEGER NOT NULL,  -- display order (0 = top)
    created_at TEXT NOT NULL
);

CREATE TABLE clients (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    group_id       TEXT NOT NULL,  -- FK → groups.id
    next_follow_up TEXT,           -- ISO date YYYY-MM-DD
    project_dir    TEXT,           -- absolute path to dummy_data/{client_id}/
    created_at     TEXT NOT NULL
);

CREATE TABLE files (
    id         TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,  -- FK → clients.id
    rel_path   TEXT NOT NULL,  -- e.g. 'people/jay.md'
    content    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(client_id, rel_path)
);

-- Seed default groups
INSERT INTO groups (id, name, position, created_at) VALUES
    ('group-active',    'Active',    0, datetime('now')),
    ('group-nurturing', 'Nurturing', 1, datetime('now'));
