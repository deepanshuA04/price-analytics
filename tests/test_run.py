from datetime import date

import httpx

from price_analytics.collector.raw_store import RawStore
from price_analytics.collector.run import collect
from price_analytics.config import Settings

CATEGORY_PAGE_1 = """
<html><body>
<article class="product_pod">
<h3><a href="../../../book-one_1/index.html">Book One</a></h3>
</article>
<ul><li class="next"><a href="page-2.html">next</a></li></ul>
</body></html>
"""

CATEGORY_PAGE_2 = """
<html><body>
<article class="product_pod">
<h3><a href="../../../book-two_2/index.html">Book Two</a></h3>
</article>
</body></html>
"""


def _product_page(upc: str, title: str, price: str) -> str:
    return f"""
<html><body>
<div class="product_main"><h1>{title}</h1></div>
<ul class="breadcrumb"><li><a href="#">Home</a></li><li><a href="#">Books</a></li>
<li><a href="#">Fiction</a></li></ul>
<p class="star-rating Three"></p>
<table class="table table-striped">
<tr><th>UPC</th><td>{upc}</td></tr>
<tr><th>Price (excl. tax)</th><td>£{price}</td></tr>
<tr><th>Price (incl. tax)</th><td>£{price}</td></tr>
<tr><th>Tax</th><td>£0.00</td></tr>
<tr><th>Availability</th><td>In stock (5 available)</td></tr>
<tr><th>Number of reviews</th><td>0</td></tr>
</table>
</body></html>
"""


PAGES = {
    "/catalogue/category/books/cat_1/index.html": CATEGORY_PAGE_1,
    "/catalogue/category/books/cat_1/page-2.html": CATEGORY_PAGE_2,
    "/catalogue/book-one_1/index.html": _product_page("upc-one", "Book One", "10.00"),
    "/catalogue/book-two_2/index.html": _product_page("upc-two", "Book Two", "20.00"),
}


def _settings(tmp_path) -> Settings:
    return Settings(
        base_url="https://example.test",
        user_agent="test-agent",
        request_delay_seconds=0.0,
        max_retries=1,
        price_drift_seed=42,
        raw_dir=tmp_path,
        categories=("cat_1",),
    )


def test_collect_discovers_and_parses_across_pagination(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=PAGES[request.url.path])

    items = collect(
        _settings(tmp_path), run_date=date(2026, 3, 1), transport=httpx.MockTransport(handler)
    )

    skus = {item.product.sku for item in items}
    assert skus == {"upc-one", "upc-two"}
    assert len(calls) == 4  # 2 category pages + 2 product pages


def test_collect_writes_raw_layer(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PAGES[request.url.path])

    run_date = date(2026, 3, 1)
    collect(_settings(tmp_path), run_date=run_date, transport=httpx.MockTransport(handler))

    raw_store = RawStore(tmp_path)
    stored_urls = raw_store.fetched_urls(run_date)
    assert len(stored_urls) == 4
    assert any(url.endswith("book-one_1/index.html") for url in stored_urls)


def test_rerunning_same_day_does_not_refetch(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=PAGES[request.url.path])

    settings = _settings(tmp_path)
    run_date = date(2026, 3, 1)

    collect(settings, run_date=run_date, transport=httpx.MockTransport(handler))
    first_run_calls = len(calls)

    collect(settings, run_date=run_date, transport=httpx.MockTransport(handler))

    assert len(calls) == first_run_calls  # second run served entirely from the raw layer


def test_collect_applies_simulated_price_drift(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=PAGES[request.url.path])

    items = collect(
        _settings(tmp_path), run_date=date(2026, 3, 1), transport=httpx.MockTransport(handler)
    )

    for item in items:
        assert item.price.list_price == item.product.price_incl_tax
        # bounded random walk: never wildly far from list price
        assert item.price.current_price > 0
        assert item.price.current_price <= item.price.list_price * 1.10
