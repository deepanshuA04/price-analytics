from datetime import date

from price_analytics.warehouse.loader import load_day
from tests.conftest import make_item


def test_load_day_inserts_fact_row(conn):
    item = make_item(sku="sku-1", collection_date=date(2026, 3, 1))

    result = load_day(conn, [item], date(2026, 3, 1))

    assert result.rows_in == 1
    assert result.rows_loaded == 1
    row = conn.execute(
        "SELECT sku, collection_date, list_price, current_price FROM fact_price_daily"
    ).fetchone()
    assert row == ("sku-1", "2026-03-01", 10.0, 9.0)


def test_reloading_same_day_does_not_duplicate_rows(conn):
    run_date = date(2026, 3, 1)
    items = [
        make_item(sku="sku-1", collection_date=run_date),
        make_item(sku="sku-2", collection_date=run_date),
    ]

    load_day(conn, items, run_date)
    load_day(conn, items, run_date)

    count = conn.execute("SELECT COUNT(*) FROM fact_price_daily").fetchone()[0]
    assert count == 2


def test_reloading_same_day_updates_price_in_place(conn):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date, current_price=9.0)], run_date)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date, current_price=8.5)], run_date)

    row = conn.execute("SELECT current_price FROM fact_price_daily WHERE sku = 'sku-1'").fetchone()
    assert row[0] == 8.5
    count = conn.execute("SELECT COUNT(*) FROM fact_price_daily WHERE sku = 'sku-1'").fetchone()[0]
    assert count == 1


def test_category_is_deduplicated_across_products(conn):
    run_date = date(2026, 3, 1)
    items = [
        make_item(sku="sku-1", category="Fiction", collection_date=run_date),
        make_item(sku="sku-2", category="Fiction", collection_date=run_date),
    ]

    load_day(conn, items, run_date)

    categories = conn.execute(
        "SELECT COUNT(*) FROM dim_category WHERE category_name = 'Fiction'"
    ).fetchone()[0]
    assert categories == 1


def test_dim_date_row_created_for_run_date(conn):
    run_date = date(2026, 3, 1)  # a Sunday
    load_day(conn, [make_item(collection_date=run_date)], run_date)

    row = conn.execute(
        "SELECT year, month, day, day_of_week, is_weekend "
        "FROM dim_date WHERE date_key = '2026-03-01'"
    ).fetchone()
    assert row == (2026, 3, 1, 0, 1)  # 2026-03-01 is a Sunday: day_of_week 0, is_weekend 1


def test_scd2_tracks_title_change_and_keeps_history(conn):
    day1 = date(2026, 3, 1)
    day2 = date(2026, 3, 2)

    load_day(conn, [make_item(sku="sku-1", title="Original Title", collection_date=day1)], day1)
    load_day(conn, [make_item(sku="sku-1", title="Retitled Edition", collection_date=day2)], day2)

    rows = conn.execute(
        "SELECT title, valid_from, valid_to, is_current FROM dim_product "
        "WHERE sku = 'sku-1' ORDER BY valid_from"
    ).fetchall()

    assert len(rows) == 2
    assert rows[0] == ("Original Title", "2026-03-01", "2026-03-02", 0)
    assert rows[1] == ("Retitled Edition", "2026-03-02", None, 1)


def test_scd2_fact_rows_point_to_the_product_version_active_that_day(conn):
    day1 = date(2026, 3, 1)
    day2 = date(2026, 3, 2)

    load_day(conn, [make_item(sku="sku-1", title="Original Title", collection_date=day1)], day1)
    load_day(conn, [make_item(sku="sku-1", title="Retitled Edition", collection_date=day2)], day2)

    titles_by_date = dict(
        conn.execute(
            """
            SELECT f.collection_date, p.title
            FROM fact_price_daily f
            JOIN dim_product p ON p.product_key = f.product_key
            WHERE f.sku = 'sku-1'
            """
        ).fetchall()
    )
    assert titles_by_date == {"2026-03-01": "Original Title", "2026-03-02": "Retitled Edition"}


def test_unchanged_product_does_not_grow_dim_product(conn):
    day1 = date(2026, 3, 1)
    day2 = date(2026, 3, 2)

    load_day(conn, [make_item(sku="sku-1", title="Same Title", collection_date=day1)], day1)
    load_day(conn, [make_item(sku="sku-1", title="Same Title", collection_date=day2)], day2)

    count = conn.execute("SELECT COUNT(*) FROM dim_product WHERE sku = 'sku-1'").fetchone()[0]
    assert count == 1
