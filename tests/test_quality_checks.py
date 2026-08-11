import sqlite3
from datetime import date, timedelta

from price_analytics.quality.checks import run_all_checks
from price_analytics.warehouse.loader import load_day
from price_analytics.warehouse.migrate import migrate
from tests.conftest import make_item


def test_all_checks_pass_on_a_clean_load(conn):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date)], run_date)

    checks = run_all_checks(conn, run_date)

    assert all(c.passed for c in checks)


def test_price_range_check_fails_on_a_negative_price(conn):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date, current_price=-5.0)], run_date)

    checks = {c.name: c for c in run_all_checks(conn, run_date)}

    assert checks["price_within_plausible_range"].passed is False


def test_price_range_check_fails_on_an_absurdly_high_price(conn):
    run_date = date(2026, 3, 1)
    item = make_item(sku="sku-1", collection_date=run_date, current_price=999999.0)
    load_day(conn, [item], run_date)

    checks = {c.name: c for c in run_all_checks(conn, run_date)}

    assert checks["price_within_plausible_range"].passed is False


def test_freshness_check_fails_when_checking_a_stale_date(conn):
    stale_date = date(2026, 3, 1)
    checked_date = date(2026, 3, 2)
    load_day(conn, [make_item(collection_date=stale_date)], stale_date)

    checks = {c.name: c for c in run_all_checks(conn, checked_date)}

    assert checks["freshness"].passed is False


def test_row_count_drift_check_fails_on_a_big_swing(conn):
    base_date = date(2026, 3, 1)
    for offset in range(5):
        d = base_date + timedelta(days=offset)
        items = [make_item(sku=f"sku-{i}", collection_date=d) for i in range(20)]
        load_day(conn, items, d)

    spike_date = base_date + timedelta(days=5)
    spike_items = [make_item(sku=f"sku-{i}", collection_date=spike_date) for i in range(2)]
    load_day(conn, spike_items, spike_date)

    checks = {c.name: c for c in run_all_checks(conn, spike_date)}

    assert checks["row_count_drift"].passed is False
    assert "today=2" in checks["row_count_drift"].detail


def test_row_count_drift_check_passes_on_a_small_swing(conn):
    base_date = date(2026, 3, 1)
    for offset in range(5):
        d = base_date + timedelta(days=offset)
        items = [make_item(sku=f"sku-{i}", collection_date=d) for i in range(20)]
        load_day(conn, items, d)

    steady_date = base_date + timedelta(days=5)
    steady_items = [make_item(sku=f"sku-{i}", collection_date=steady_date) for i in range(19)]
    load_day(conn, steady_items, steady_date)

    checks = {c.name: c for c in run_all_checks(conn, steady_date)}

    assert checks["row_count_drift"].passed is True


def test_no_duplicate_natural_keys_check_passes_on_normal_data(conn):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date)], run_date)

    checks = {c.name: c for c in run_all_checks(conn, run_date)}

    assert checks["no_duplicate_natural_keys"].passed is True


def test_referential_integrity_check_fails_on_a_dangling_key(db_path):
    # Bypass the loader (and its enabled foreign_keys pragma) to simulate the
    # kind of corruption this check exists to catch: a fact row pointing at a
    # dimension key that doesn't exist.
    raw_conn = sqlite3.connect(db_path)
    migrate(raw_conn)
    run_date = date(2026, 3, 1)
    raw_conn.execute(
        "INSERT INTO fact_price_daily "
        "(sku, collection_date, product_key, category_key, list_price, current_price, "
        " currency, available_count, loaded_at) "
        "VALUES ('sku-x', ?, 9999, 9999, 10.0, 9.0, 'GBP', 1, '2026-03-01T00:00:00+00:00')",
        (run_date.isoformat(),),
    )
    raw_conn.commit()

    checks = {c.name: c for c in run_all_checks(raw_conn, run_date)}

    assert checks["referential_integrity"].passed is False
