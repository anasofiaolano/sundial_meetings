# Database Migrations

Sundial uses a simple file-based migration system. Each schema change is a
numbered SQL file in `backend/migrations/`. A lightweight runner applies
them in order and tracks which have run.

## Running migrations

```bash
# Apply all pending migrations
python backend/migrate.py

# Check status (which have run, which are pending)
python backend/migrate.py --status
```

Migrations are **manual** — they are not run automatically on server startup.
Run them as a deliberate step before (re)starting the server after a deploy.

## How it works

- `backend/migrate.py` reads all `*.sql` files from `backend/migrations/`, sorted by filename
- A `schema_migrations` table in `jobs.db` tracks which filenames have been applied
- Each migration runs exactly once; already-applied files are skipped
- If a migration fails, the script exits immediately with an error — nothing after it runs

## Adding a migration

1. Create a new file in `backend/migrations/` with the next number prefix:
   ```
   0003_my_change.sql
   ```
2. Write plain SQL — `CREATE TABLE`, `ALTER TABLE`, `INSERT`, etc.
3. Run `python backend/migrate.py` to apply it.

**Never edit an already-applied migration file.** If you need to change something,
write a new migration that makes the correction.

## File index

| File | Description |
|------|-------------|
| `0001_initial.sql` | Full `jobs` table — all columns through phase 7 |
| `0002_phase8_clients.sql` | `groups`, `clients`, `files` tables + `client_id` on `jobs` |

## Existing databases

If `jobs.db` already exists (from before the migration system was introduced),
run `migrate.py` once. It will skip `0001_initial.sql` gracefully (the `jobs`
table already exists) and apply only the files that add new things.

> SQLite's `CREATE TABLE IF NOT EXISTS` in `0001` means re-running it on an
> existing DB is a no-op for the table itself. The `ALTER TABLE` statements in
> later migrations will fail if the column already exists — write them
> defensively if needed (see SQLite docs on `ALTER TABLE`).
