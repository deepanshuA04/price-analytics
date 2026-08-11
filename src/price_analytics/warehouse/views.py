from __future__ import annotations

import sqlite3
from pathlib import Path

from price_analytics.warehouse.db import REPO_ROOT

VIEWS_DIR = REPO_ROOT / "sql" / "views"


def apply_views(conn: sqlite3.Connection, views_dir: Path = VIEWS_DIR) -> list[str]:
    """(Re)create every view from sql/views/*.sql, in filename order.

    Unlike migrate(), this always re-applies every file: views hold no data, so
    there's no cost to keeping them in lockstep with whatever is checked in, and
    numbered filenames handle dependency order for views that build on others.
    """
    applied = []
    for path in sorted(views_dir.glob("*.sql")):
        conn.executescript(path.read_text(encoding="utf-8"))
        applied.append(path.name)
    conn.commit()
    return applied
