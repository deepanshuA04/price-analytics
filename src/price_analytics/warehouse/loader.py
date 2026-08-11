from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from price_analytics.collector.records import CollectedItem


@dataclass(frozen=True)
class LoadResult:
    rows_in: int
    rows_loaded: int


def load_day(conn: sqlite3.Connection, items: list[CollectedItem], run_date: date) -> LoadResult:
    """Idempotent upsert of one collection day into the warehouse.

    Natural key (sku, collection_date) means re-running the same day's items
    updates the existing fact row in place rather than duplicating it. Product
    title/category changes are kept as slowly-changing history in dim_product
    instead of being overwritten.
    """
    _ensure_date(conn, run_date)
    rows_loaded = 0
    for item in items:
        category_key = _upsert_category(conn, item.product.category)
        product_key = _upsert_product_scd(conn, item.product, category_key, run_date)
        _upsert_fact(conn, item, product_key, category_key, run_date)
        rows_loaded += 1
    conn.commit()
    return LoadResult(rows_in=len(items), rows_loaded=rows_loaded)


def _upsert_category(conn: sqlite3.Connection, category_name: str) -> int:
    conn.execute(
        "INSERT INTO dim_category (category_name) VALUES (?) "
        "ON CONFLICT (category_name) DO NOTHING",
        (category_name,),
    )
    row = conn.execute(
        "SELECT category_key FROM dim_category WHERE category_name = ?", (category_name,)
    ).fetchone()
    return row[0]


def _upsert_product_scd(
    conn: sqlite3.Connection, product, category_key: int, run_date: date
) -> int:
    run_date_iso = run_date.isoformat()
    current = conn.execute(
        "SELECT product_key, title, category_key FROM dim_product "
        "WHERE sku = ? AND is_current = 1",
        (product.sku,),
    ).fetchone()

    if current is not None:
        product_key, current_title, current_category_key = current
        if current_title == product.title and current_category_key == category_key:
            return product_key
        conn.execute(
            "UPDATE dim_product SET valid_to = ?, is_current = 0 WHERE product_key = ?",
            (run_date_iso, product_key),
        )

    cur = conn.execute(
        "INSERT INTO dim_product "
        "(sku, title, category_key, rating, source_url, valid_from, valid_to, is_current) "
        "VALUES (?, ?, ?, ?, ?, ?, NULL, 1)",
        (
            product.sku,
            product.title,
            category_key,
            product.rating,
            product.source_url,
            run_date_iso,
        ),
    )
    return cur.lastrowid


def _upsert_fact(
    conn: sqlite3.Connection,
    item: CollectedItem,
    product_key: int,
    category_key: int,
    run_date: date,
) -> None:
    conn.execute(
        """
        INSERT INTO fact_price_daily
            (sku, collection_date, product_key, category_key, list_price, current_price,
             currency, available_count, loaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (sku, collection_date) DO UPDATE SET
            product_key = excluded.product_key,
            category_key = excluded.category_key,
            list_price = excluded.list_price,
            current_price = excluded.current_price,
            currency = excluded.currency,
            available_count = excluded.available_count,
            loaded_at = excluded.loaded_at
        """,
        (
            item.product.sku,
            run_date.isoformat(),
            product_key,
            category_key,
            item.price.list_price,
            item.price.current_price,
            item.price.currency,
            item.product.available_count,
            datetime.now(UTC).isoformat(),
        ),
    )


def _ensure_date(conn: sqlite3.Connection, d: date) -> None:
    iso = d.isoformat()
    exists = conn.execute("SELECT 1 FROM dim_date WHERE date_key = ?", (iso,)).fetchone()
    if exists:
        return
    conn.execute(
        "INSERT INTO dim_date "
        "(date_key, year, month, day, day_of_week, week_of_year, is_weekend) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            iso,
            d.year,
            d.month,
            d.day,
            (d.weekday() + 1) % 7,  # Sunday=0 .. Saturday=6, matching SQLite strftime('%w')
            int(d.strftime("%W")),
            1 if d.weekday() >= 5 else 0,
        ),
    )
