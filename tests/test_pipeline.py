import sqlite3
from datetime import date

import pytest

from price_analytics.pipeline import PipelineFailure, run_pipeline
from tests.conftest import make_item


def test_run_pipeline_succeeds_and_logs_the_run(db_path):
    run_date = date(2026, 3, 1)
    items = [make_item(sku=f"sku-{i}", collection_date=run_date) for i in range(10)]

    summary = run_pipeline(run_date=run_date, items=items, db_path=db_path)

    assert summary.status == "success"
    assert summary.rows_in == 10
    assert summary.rows_loaded == 10

    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT status, rows_in, rows_loaded, rows_rejected, checks_passed, checks_failed "
        "FROM run_log"
    ).fetchone()
    assert row == ("success", 10, 10, 0, 6, 0)


def test_seeded_bad_data_fails_the_run(db_path):
    """The verification requirement from the project spec: feed the pipeline
    deliberately bad data and prove it fails loudly instead of loading it."""
    run_date = date(2026, 3, 1)
    bad_items = [make_item(sku="sku-bad", collection_date=run_date, current_price=-1.0)]

    with pytest.raises(PipelineFailure, match="price_within_plausible_range"):
        run_pipeline(run_date=run_date, items=bad_items, db_path=db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status, checks_failed, failed_check_names FROM run_log").fetchone()
    assert row[0] == "failed"
    assert row[1] > 0
    assert "price_within_plausible_range" in row[2]

    # the bad row still lands in the fact table - the gate fails loudly rather
    # than silently dropping it, which is the point: someone has to look.
    fact_count = conn.execute("SELECT COUNT(*) FROM fact_price_daily").fetchone()[0]
    assert fact_count == 1


def test_an_unhandled_error_before_checks_still_gets_logged_as_failed(db_path, monkeypatch):
    import price_analytics.pipeline as pipeline_module

    def _boom(conn, items, run_date):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline_module, "load_day", _boom)

    with pytest.raises(RuntimeError):
        run_pipeline(run_date=date(2026, 3, 1), items=[make_item()], db_path=db_path)

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT status FROM run_log").fetchone()
    assert row[0] == "failed"
