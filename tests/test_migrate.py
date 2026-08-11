from price_analytics.warehouse.db import connect
from price_analytics.warehouse.migrate import applied_migrations, migrate


def test_migrate_creates_all_tables(tmp_path):
    conn = connect(tmp_path / "test.db")

    migrate(conn)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {
        "dim_category",
        "dim_product",
        "dim_date",
        "fact_price_daily",
        "run_log",
        "schema_migrations",
    } <= tables


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "test.db")

    first = migrate(conn)
    second = migrate(conn)

    assert len(first) == 5
    assert second == []
    assert len(applied_migrations(conn)) == 5


def test_fact_price_daily_primary_key_is_sku_and_date(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)

    columns = conn.execute("PRAGMA table_info(fact_price_daily)").fetchall()
    # col[5] is the PK ordinal; 0 means "not part of the primary key"
    pk_columns = {col[1] for col in columns if col[5] > 0}
    assert pk_columns == {"sku", "collection_date"}
