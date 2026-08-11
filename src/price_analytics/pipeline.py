from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from price_analytics.collector.records import CollectedItem
from price_analytics.collector.run import collect
from price_analytics.config import load_settings
from price_analytics.quality.checks import CheckResult, run_all_checks
from price_analytics.warehouse.db import DEFAULT_DB_PATH, connect
from price_analytics.warehouse.export import EXPORT_DIR, export_views_to_csv
from price_analytics.warehouse.loader import load_day
from price_analytics.warehouse.migrate import migrate
from price_analytics.warehouse.views import apply_views

logger = logging.getLogger(__name__)


class PipelineFailure(Exception):
    """Raised when a run's data-quality checks fail. Left uncaught, this fails
    the process (and therefore the GitHub Actions run) loudly rather than
    silently loading bad data."""


@dataclass(frozen=True)
class RunSummary:
    run_date: date
    rows_in: int
    rows_loaded: int
    checks: list[CheckResult]
    status: str


def run_pipeline(
    run_date: date | None = None,
    items: list[CollectedItem] | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    export_dir: Path = EXPORT_DIR,
) -> RunSummary:
    """Collect -> load -> quality-gate one day, and record the outcome in run_log.

    `items` lets callers (tests, or a re-run against already-fetched raw data)
    skip live collection; `db_path` lets tests point at a throwaway database
    instead of the real warehouse file. The dashboard CSV export runs whether
    the checks pass or fail, so the status tile can show a failed run instead
    of just going stale.
    """
    run_date = run_date or date.today()
    conn = connect(db_path)
    migrate(conn)
    apply_views(conn)

    started_at = datetime.now(UTC)
    run_id = _start_run_log(conn, run_date, started_at)

    try:
        if items is None:
            items = collect(load_settings(), run_date=run_date)
        result = load_day(conn, items, run_date)
        checks = run_all_checks(conn, run_date)
    except Exception:
        _finish_run_log(
            conn,
            run_id,
            started_at,
            rows_in=0,
            rows_loaded=0,
            checks=[],
            status="failed",
        )
        export_views_to_csv(conn, export_dir)
        conn.close()
        raise

    checks_failed = [c for c in checks if not c.passed]
    status = "success" if not checks_failed else "failed"
    _finish_run_log(
        conn,
        run_id,
        started_at,
        rows_in=result.rows_in,
        rows_loaded=result.rows_loaded,
        checks=checks,
        status=status,
    )
    export_views_to_csv(conn, export_dir)
    conn.close()

    if checks_failed:
        detail = "; ".join(f"{c.name}: {c.detail}" for c in checks_failed)
        raise PipelineFailure(f"data-quality checks failed for {run_date.isoformat()} -> {detail}")

    logger.info(
        "pipeline succeeded for %s: %d/%d rows loaded",
        run_date.isoformat(),
        result.rows_loaded,
        result.rows_in,
    )
    return RunSummary(run_date, result.rows_in, result.rows_loaded, checks, status)


def _start_run_log(conn, run_date: date, started_at: datetime) -> int:
    cur = conn.execute(
        "INSERT INTO run_log (run_date, started_at, status) VALUES (?, ?, 'running')",
        (run_date.isoformat(), started_at.isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def _finish_run_log(
    conn,
    run_id: int,
    started_at: datetime,
    rows_in: int,
    rows_loaded: int,
    checks: list[CheckResult],
    status: str,
) -> None:
    finished_at = datetime.now(UTC)
    checks_failed = [c for c in checks if not c.passed]
    conn.execute(
        """
        UPDATE run_log
        SET finished_at = ?, rows_in = ?, rows_loaded = ?, rows_rejected = ?,
            checks_passed = ?, checks_failed = ?, failed_check_names = ?,
            status = ?, duration_seconds = ?
        WHERE run_id = ?
        """,
        (
            finished_at.isoformat(),
            rows_in,
            rows_loaded,
            rows_in - rows_loaded,
            len(checks) - len(checks_failed),
            len(checks_failed),
            json.dumps([c.name for c in checks_failed]),
            status,
            (finished_at - started_at).total_seconds(),
            run_id,
        ),
    )
    conn.commit()


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_pipeline()
    except PipelineFailure as exc:
        logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
