from __future__ import annotations

import sqlite3
from pathlib import Path

from price_analytics.warehouse.db import MIGRATIONS_DIR


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    ensure_migrations_table(conn)
    return {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}


def migrate(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply any *.sql files in migrations_dir not yet recorded, in filename order.

    Safe to call on every run: already-applied migrations are skipped, so this
    doubles as the "create the schema if it doesn't exist yet" step.
    """
    ensure_migrations_table(conn)
    already_applied = applied_migrations(conn)
    applied_now = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in already_applied:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (?)", (path.name,))
        conn.commit()
        applied_now.append(path.name)
    return applied_now
