from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from price_analytics.warehouse.db import REPO_ROOT

EXPORT_DIR = REPO_ROOT / "powerbi" / "data"

# The wide/summary views the dashboard reads from - not the five narrower
# per-metric views they're built from, so Power BI gets one file per page
# rather than something it has to re-join itself.
VIEWS_TO_EXPORT = (
    "v_sku_daily_metrics",
    "v_category_overview",
    "v_repricing_shortlist",
    "v_run_log_status",
)


def export_views_to_csv(
    conn: sqlite3.Connection, export_dir: Path = EXPORT_DIR
) -> list[Path]:
    """Snapshot each dashboard-facing view to its own CSV.

    Power BI Desktop has no native SQLite connector and getting an ODBC driver
    working is a heavier lift than this project needs (see powerbi/README.md),
    so the dashboard reads these files with Get Data > Text/CSV instead of
    connecting to the .db directly. Re-run this (or the pipeline, which calls
    it automatically) and hit Refresh in Power BI to pick up new data.
    """
    export_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for view_name in VIEWS_TO_EXPORT:
        cursor = conn.execute(f"SELECT * FROM {view_name}")
        columns = [description[0] for description in cursor.description]
        path = export_dir / f"{view_name}.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            writer.writerows(cursor.fetchall())
        written.append(path)
    return written
