from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

MIN_PLAUSIBLE_PRICE = 0.01
MAX_PLAUSIBLE_PRICE = 500.00  # books.toscrape.com prices top out well under this
ROW_COUNT_DRIFT_THRESHOLD = 0.30
TRAILING_WINDOW_RUNS = 14


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_all_checks(conn: sqlite3.Connection, run_date: date) -> list[CheckResult]:
    return [
        check_no_nulls_in_required_columns(conn, run_date),
        check_price_range(conn, run_date),
        check_freshness(conn, run_date),
        check_row_count_drift(conn, run_date),
        check_no_duplicate_natural_keys(conn, run_date),
        check_referential_integrity(conn, run_date),
    ]


def check_no_nulls_in_required_columns(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    bad = conn.execute(
        """
        SELECT COUNT(*) FROM fact_price_daily
        WHERE collection_date = ?
          AND (sku IS NULL OR product_key IS NULL OR category_key IS NULL
               OR list_price IS NULL OR current_price IS NULL)
        """,
        (run_date.isoformat(),),
    ).fetchone()[0]
    return CheckResult(
        "no_nulls_in_required_columns", bad == 0, f"{bad} rows with a null required column"
    )


def check_price_range(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    bad = conn.execute(
        """
        SELECT COUNT(*) FROM fact_price_daily
        WHERE collection_date = ?
          AND (current_price < ? OR current_price > ? OR list_price < ? OR list_price > ?)
        """,
        (
            run_date.isoformat(),
            MIN_PLAUSIBLE_PRICE,
            MAX_PLAUSIBLE_PRICE,
            MIN_PLAUSIBLE_PRICE,
            MAX_PLAUSIBLE_PRICE,
        ),
    ).fetchone()[0]
    return CheckResult(
        "price_within_plausible_range",
        bad == 0,
        f"{bad} rows outside £{MIN_PLAUSIBLE_PRICE:.2f}-£{MAX_PLAUSIBLE_PRICE:.2f}",
    )


def check_freshness(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    max_date = conn.execute("SELECT MAX(collection_date) FROM fact_price_daily").fetchone()[0]
    passed = max_date == run_date.isoformat()
    return CheckResult(
        "freshness", passed, f"max collection_date is {max_date}, expected {run_date.isoformat()}"
    )


def check_row_count_drift(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    today_count = conn.execute(
        "SELECT COUNT(*) FROM fact_price_daily WHERE collection_date = ?",
        (run_date.isoformat(),),
    ).fetchone()[0]

    previous_counts = [
        row[0]
        for row in conn.execute(
            """
            SELECT COUNT(*) FROM fact_price_daily
            WHERE collection_date < ?
            GROUP BY collection_date
            ORDER BY collection_date DESC
            LIMIT ?
            """,
            (run_date.isoformat(), TRAILING_WINDOW_RUNS),
        ).fetchall()
    ]
    if not previous_counts:
        return CheckResult("row_count_drift", True, "no prior runs to compare against")

    median = sorted(previous_counts)[len(previous_counts) // 2]
    if median == 0:
        return CheckResult("row_count_drift", True, "trailing median row count is 0")

    drift = abs(today_count - median) / median
    passed = drift <= ROW_COUNT_DRIFT_THRESHOLD
    return CheckResult(
        "row_count_drift",
        passed,
        f"today={today_count}, trailing median={median}, drift={drift:.1%}",
    )


def check_no_duplicate_natural_keys(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    bad = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT sku FROM fact_price_daily
            WHERE collection_date = ?
            GROUP BY sku HAVING COUNT(*) > 1
        )
        """,
        (run_date.isoformat(),),
    ).fetchone()[0]
    return CheckResult(
        "no_duplicate_natural_keys", bad == 0, f"{bad} duplicated (sku, collection_date) keys"
    )


def check_referential_integrity(conn: sqlite3.Connection, run_date: date) -> CheckResult:
    bad = conn.execute(
        """
        SELECT COUNT(*) FROM fact_price_daily f
        WHERE f.collection_date = ?
          AND (
              NOT EXISTS (SELECT 1 FROM dim_product p WHERE p.product_key = f.product_key)
              OR NOT EXISTS (SELECT 1 FROM dim_category c WHERE c.category_key = f.category_key)
          )
        """,
        (run_date.isoformat(),),
    ).fetchone()[0]
    return CheckResult(
        "referential_integrity", bad == 0, f"{bad} fact rows with a dangling dimension key"
    )
