#!/usr/bin/env python3
# migrate.py
#
# Applies any unapplied SQL migrations from backend/migrations/ to jobs.db.
# Migrations run in filename order (0001_, 0002_, ...) and are tracked in a
# schema_migrations table so each file runs exactly once.
#
# Usage:
#   python backend/migrate.py            # apply all pending migrations
#   python backend/migrate.py --status   # show which migrations have run

import argparse
import sqlite3
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DB_PATH        = Path(__file__).parent / "jobs.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_tracking_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


def _applied(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT filename FROM schema_migrations").fetchall()}


def _migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations. Returns the count applied."""
    _ensure_tracking_table(conn)
    applied = _applied(conn)
    pending = [f for f in _migration_files() if f.name not in applied]

    if not pending:
        print("Already up to date.")
        return 0

    for path in pending:
        print(f"  Applying {path.name} ...", end=" ")
        sql = path.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,)
            )
            print("done")
        except Exception as e:
            print(f"FAILED\n\nError in {path.name}:\n  {e}")
            sys.exit(1)

    return len(pending)


def print_status(conn: sqlite3.Connection):
    _ensure_tracking_table(conn)
    applied = _applied(conn)
    all_files = _migration_files()

    if not all_files:
        print("No migration files found.")
        return

    for path in all_files:
        status = "applied" if path.name in applied else "pending"
        print(f"  [{status:7}]  {path.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DB migrations for Sundial.")
    parser.add_argument("--status", action="store_true", help="Show migration status without applying")
    args = parser.parse_args()

    conn = _connect()

    if args.status:
        print_status(conn)
    else:
        n = run_migrations(conn)
        if n:
            print(f"\n{n} migration(s) applied.")

    conn.close()
