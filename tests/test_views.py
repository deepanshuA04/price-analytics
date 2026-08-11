"""Tests for sql/views/*.sql against a small, hand-computable fixture.

Fixture: 5 days (2026-01-01..05), 2 categories.
  Fiction:     SKU-A list=20, prices [10, 12, 11, 9, 15]
               SKU-B list=20, prices [20, 20, 20, 20, 25]
  Nonfiction:  SKU-C list=20, prices [5, 5, 6, 7, 8]

Every expected value below was computed by hand from that table, not copied
from the view's own output, so these tests catch real arithmetic mistakes.
"""

from datetime import date, timedelta

from price_analytics.warehouse.loader import load_day
from tests.conftest import make_item

DAY1 = date(2026, 1, 1)
FICTION_A_PRICES = [10, 12, 11, 9, 15]
FICTION_B_PRICES = [20, 20, 20, 20, 25]
NONFICTION_C_PRICES = [5, 5, 6, 7, 8]


def _load_fixture(conn):
    for offset in range(5):
        d = DAY1 + timedelta(days=offset)
        items = [
            make_item(
                sku="SKU-A", category="Fiction", list_price=20.0,
                current_price=float(FICTION_A_PRICES[offset]), collection_date=d,
            ),
            make_item(
                sku="SKU-B", category="Fiction", list_price=20.0,
                current_price=float(FICTION_B_PRICES[offset]), collection_date=d,
            ),
            make_item(
                sku="SKU-C", category="Nonfiction", list_price=20.0,
                current_price=float(NONFICTION_C_PRICES[offset]), collection_date=d,
            ),
        ]
        load_day(conn, items, d)


def test_moving_average_grain_is_one_row_per_sku_per_day(conn):
    _load_fixture(conn)

    count = conn.execute("SELECT COUNT(*) FROM v_price_moving_avg").fetchone()[0]
    assert count == 15  # 3 skus x 5 days


def test_moving_average_on_last_day_uses_all_five_days_seen_so_far(conn):
    _load_fixture(conn)

    row = conn.execute(
        "SELECT avg_price_7d, avg_price_30d, days_in_30d_window "
        "FROM v_price_moving_avg WHERE sku = 'SKU-A' AND collection_date = '2026-01-05'"
    ).fetchone()

    expected_avg = sum(FICTION_A_PRICES) / 5  # 11.4
    assert row == (expected_avg, expected_avg, 5)


def test_day_over_day_and_week_over_week_change(conn):
    _load_fixture(conn)

    row = conn.execute(
        "SELECT prior_day_price, day_over_day_change, day_over_day_change_pct, "
        "prior_week_price, week_over_week_change "
        "FROM v_price_change WHERE sku = 'SKU-A' AND collection_date = '2026-01-05'"
    ).fetchone()

    # day5=15, day4=9 -> +6, +66.67%; only 5 days exist so LAG(7) is NULL
    assert row == (9.0, 6.0, 66.67, None, None)


def test_category_rank_and_percentile_on_last_day(conn):
    _load_fixture(conn)

    rows = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT sku, category_price_rank, category_price_percentile, category_sku_count "
            "FROM v_category_rank "
            "WHERE collection_date = '2026-01-05' AND category_name = 'Fiction'"
        ).fetchall()
    }

    # Fiction day5: SKU-B=25 (most expensive, rank 1, percentile 1.0)
    #               SKU-A=15 (cheaper, rank 2, percentile 0.0)
    assert rows["SKU-B"] == (1, 1.0, 2)
    assert rows["SKU-A"] == (2, 0.0, 2)


def test_discount_depth_and_category_median(conn):
    _load_fixture(conn)

    rows = {
        r[0]: r[1:]
        for r in conn.execute(
            "SELECT sku, discount_depth, category_median_price, premium_to_category_median "
            "FROM v_discount_depth "
            "WHERE collection_date = '2026-01-05' AND category_name = 'Fiction'"
        ).fetchall()
    }

    # median of [15, 25] = 20.0
    assert rows["SKU-A"] == (0.25, 20.0, -0.25)  # (20-15)/20=0.25; (15-20)/20=-0.25
    assert rows["SKU-B"] == (-0.25, 20.0, 0.25)  # (20-25)/20=-0.25; (25-20)/20=0.25

    # Nonfiction has only SKU-C, so its own price is the category median
    nonfiction_row = conn.execute(
        "SELECT category_median_price, premium_to_category_median FROM v_discount_depth "
        "WHERE sku = 'SKU-C' AND collection_date = '2026-01-05'"
    ).fetchone()
    assert nonfiction_row == (8.0, 0.0)


def test_price_volatility_matches_hand_computed_sample_stddev(conn):
    _load_fixture(conn)

    # SKU-B is constant at 20 for 4 days then jumps to 25 -> nonzero, hand-computable stddev
    volatility_b = conn.execute(
        "SELECT price_volatility_30d FROM v_price_volatility "
        "WHERE sku = 'SKU-B' AND collection_date = '2026-01-05'"
    ).fetchone()[0]
    assert volatility_b == 2.2361  # sqrt(sample variance of [20,20,20,20,25]) rounded to 4dp

    volatility_a = conn.execute(
        "SELECT price_volatility_30d FROM v_price_volatility "
        "WHERE sku = 'SKU-A' AND collection_date = '2026-01-05'"
    ).fetchone()[0]
    assert volatility_a == 2.3022  # sqrt(sample variance of [10,12,11,9,15]) rounded to 4dp


def test_price_volatility_is_null_on_a_skus_first_day(conn):
    _load_fixture(conn)

    volatility = conn.execute(
        "SELECT price_volatility_30d FROM v_price_volatility "
        "WHERE sku = 'SKU-A' AND collection_date = '2026-01-01'"
    ).fetchone()[0]
    assert volatility is None


def test_sku_daily_metrics_preserves_the_sku_per_day_grain(conn):
    _load_fixture(conn)

    count = conn.execute("SELECT COUNT(*) FROM v_sku_daily_metrics").fetchone()[0]
    distinct_keys = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT sku, collection_date FROM v_sku_daily_metrics)"
    ).fetchone()[0]
    assert count == 15
    assert distinct_keys == 15


def test_category_overview_grain_and_price_index(conn):
    _load_fixture(conn)

    count = conn.execute("SELECT COUNT(*) FROM v_category_overview").fetchone()[0]
    assert count == 10  # 2 categories x 5 days

    fiction_day5 = conn.execute(
        "SELECT avg_price, price_index, sku_count, price_spread FROM v_category_overview "
        "WHERE category_name = 'Fiction' AND collection_date = '2026-01-05'"
    ).fetchone()
    # day1 avg = (10+20)/2 = 15 (base); day5 avg = (15+25)/2 = 20 -> index 133.33
    assert fiction_day5 == (20.0, 133.33, 2, 10.0)

    nonfiction_day5 = conn.execute(
        "SELECT avg_price, price_index FROM v_category_overview "
        "WHERE category_name = 'Nonfiction' AND collection_date = '2026-01-05'"
    ).fetchone()
    # day1 avg = 5 (base); day5 = 8 -> index 160.0
    assert nonfiction_day5 == (8.0, 160.0)


def test_repricing_shortlist_only_includes_skus_over_15_percent_premium(conn):
    _load_fixture(conn)

    rows = conn.execute(
        "SELECT sku, premium_to_category_median FROM v_repricing_shortlist"
    ).fetchall()

    # Only SKU-B (25% premium) clears the >15% bar on the latest day; SKU-A is
    # below median and SKU-C is its own category's only member (0% premium).
    assert rows == [("SKU-B", 0.25)]


def test_repricing_shortlist_only_covers_the_latest_collection_date(conn):
    _load_fixture(conn)

    dates = {
        r[0] for r in conn.execute("SELECT DISTINCT collection_date FROM v_repricing_shortlist")
    }
    assert dates <= {"2026-01-05"}


def test_run_log_status_is_always_exactly_one_row(conn):
    row = conn.execute("SELECT * FROM v_run_log_status").fetchone()
    assert row is not None
    assert conn.execute("SELECT COUNT(*) FROM v_run_log_status").fetchone()[0] == 1


def test_run_log_status_reliability_reflects_successes_and_failures(conn):
    conn.execute(
        "INSERT INTO run_log (run_date, started_at, status) VALUES "
        "('2026-01-01', '2026-01-01T00:00:00+00:00', 'success')"
    )
    conn.execute(
        "INSERT INTO run_log (run_date, started_at, status) VALUES "
        "('2026-01-02', '2026-01-02T00:00:00+00:00', 'failed')"
    )
    conn.commit()

    row = conn.execute(
        "SELECT total_runs, successful_runs, reliability_pct, latest_run_status "
        "FROM v_run_log_status"
    ).fetchone()

    assert row == (2, 1, 50.0, "failed")
