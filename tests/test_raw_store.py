import gzip
import json
from datetime import date

from price_analytics.collector.raw_store import RawStore


def test_append_and_read_roundtrip(tmp_path):
    store = RawStore(tmp_path)
    run_date = date(2026, 1, 1)

    store.append(run_date, "https://example.test/a", 200, "<html>a</html>")
    store.append(run_date, "https://example.test/b", 200, "<html>b</html>")

    records = list(store.read(run_date))
    assert [r.url for r in records] == ["https://example.test/a", "https://example.test/b"]
    assert records[0].html == "<html>a</html>"
    assert records[0].status_code == 200


def test_fetched_urls_supports_resumability(tmp_path):
    store = RawStore(tmp_path)
    run_date = date(2026, 1, 1)

    store.append(run_date, "https://example.test/a", 200, "<html>a</html>")

    assert store.fetched_urls(run_date) == {"https://example.test/a"}


def test_read_on_missing_date_yields_nothing(tmp_path):
    store = RawStore(tmp_path)

    assert list(store.read(date(2026, 1, 1))) == []
    assert store.fetched_urls(date(2026, 1, 1)) == set()


def test_separate_dates_do_not_collide(tmp_path):
    store = RawStore(tmp_path)

    store.append(date(2026, 1, 1), "https://example.test/a", 200, "day1")
    store.append(date(2026, 1, 2), "https://example.test/a", 200, "day2")

    assert list(store.read(date(2026, 1, 1)))[0].html == "day1"
    assert list(store.read(date(2026, 1, 2)))[0].html == "day2"


def test_file_on_disk_is_gzip_named_by_date(tmp_path):
    store = RawStore(tmp_path)
    run_date = date(2026, 1, 1)

    store.append(run_date, "https://example.test/a", 200, "<html>a</html>")

    path = store.path_for(run_date)
    assert path.name == "2026-01-01.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        record = json.loads(fh.readline())
    assert record["url"] == "https://example.test/a"
