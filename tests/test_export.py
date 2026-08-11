import csv
from datetime import date

from price_analytics.warehouse.export import export_views_to_csv
from price_analytics.warehouse.loader import load_day
from tests.conftest import make_item


def test_export_writes_one_csv_per_dashboard_view(conn, tmp_path):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date)], run_date)

    export_dir = tmp_path / "export"
    written = export_views_to_csv(conn, export_dir)

    names = {path.name for path in written}
    assert names == {
        "v_sku_daily_metrics.csv",
        "v_category_overview.csv",
        "v_repricing_shortlist.csv",
        "v_run_log_status.csv",
    }
    for path in written:
        assert path.exists()


def test_exported_csv_has_a_header_and_matches_the_view(conn, tmp_path):
    run_date = date(2026, 3, 1)
    load_day(conn, [make_item(sku="sku-1", collection_date=run_date)], run_date)

    export_dir = tmp_path / "export"
    export_views_to_csv(conn, export_dir)

    with (export_dir / "v_sku_daily_metrics.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    view_row_count = conn.execute("SELECT COUNT(*) FROM v_sku_daily_metrics").fetchone()[0]
    assert len(rows) - 1 == view_row_count  # minus the header row
    assert "sku" in rows[0]
    assert "collection_date" in rows[0]


def test_export_overwrites_stale_data_on_rerun(conn, tmp_path):
    run_date = date(2026, 3, 1)
    export_dir = tmp_path / "export"

    load_day(conn, [make_item(sku="sku-1", collection_date=run_date)], run_date)
    export_views_to_csv(conn, export_dir)

    load_day(conn, [make_item(sku="sku-2", collection_date=run_date)], run_date)
    export_views_to_csv(conn, export_dir)

    with (export_dir / "v_sku_daily_metrics.csv").open(newline="", encoding="utf-8") as fh:
        skus = {row["sku"] for row in csv.DictReader(fh)}
    assert skus == {"sku-1", "sku-2"}
