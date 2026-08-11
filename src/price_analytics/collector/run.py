from __future__ import annotations

import logging
from datetime import date
from urllib.parse import urljoin

import httpx

from price_analytics.collector.fetcher import PoliteFetcher
from price_analytics.collector.parser import parse_category_page, parse_product_page
from price_analytics.collector.price_simulator import simulate_price
from price_analytics.collector.raw_store import RawStore
from price_analytics.collector.records import CollectedItem, PriceObservation
from price_analytics.config import Settings, load_settings

logger = logging.getLogger(__name__)

CATEGORY_PATH_TEMPLATE = "catalogue/category/books/{slug}/index.html"


def collect(
    settings: Settings,
    run_date: date | None = None,
    transport: httpx.BaseTransport | None = None,
) -> list[CollectedItem]:
    run_date = run_date or date.today()
    raw_store = RawStore(settings.raw_dir)
    cache = {record.url: record.html for record in raw_store.read(run_date)}
    items: list[CollectedItem] = []

    with PoliteFetcher(
        user_agent=settings.user_agent,
        delay_seconds=settings.request_delay_seconds,
        max_retries=settings.max_retries,
        transport=transport,
    ) as fetcher:
        for slug in settings.categories:
            category_url = urljoin(
                settings.base_url + "/", CATEGORY_PATH_TEMPLATE.format(slug=slug)
            )
            product_urls = _discover_category(fetcher, raw_store, run_date, cache, category_url)
            logger.info("category %s: %d products", slug, len(product_urls))

            for product_url in product_urls:
                html = _fetch_and_store(fetcher, raw_store, run_date, cache, product_url)
                product = parse_product_page(html, product_url)
                current_price = simulate_price(
                    list_price=product.price_incl_tax,
                    sku=product.sku,
                    collection_date=run_date,
                    seed=settings.price_drift_seed,
                )
                observation = PriceObservation(
                    sku=product.sku,
                    collection_date=run_date,
                    list_price=product.price_incl_tax,
                    current_price=current_price,
                )
                items.append(CollectedItem(product=product, price=observation))

    logger.info("collected %d products for %s", len(items), run_date.isoformat())
    return items


def _discover_category(
    fetcher: PoliteFetcher,
    raw_store: RawStore,
    run_date: date,
    cache: dict[str, str],
    category_url: str,
) -> list[str]:
    product_urls: list[str] = []
    page_url: str | None = category_url
    while page_url is not None:
        html = _fetch_and_store(fetcher, raw_store, run_date, cache, page_url)
        hrefs, next_href = parse_category_page(html)
        product_urls.extend(urljoin(page_url, href) for href in hrefs)
        page_url = urljoin(page_url, next_href) if next_href else None
    return product_urls


def _fetch_and_store(
    fetcher: PoliteFetcher,
    raw_store: RawStore,
    run_date: date,
    cache: dict[str, str],
    url: str,
) -> str:
    if url in cache:
        return cache[url]
    response = fetcher.get(url)
    raw_store.append(run_date, url, response.status_code, response.text)
    cache[url] = response.text
    return response.text


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = load_settings()
    items = collect(settings)
    print(f"collected {len(items)} products across {len(settings.categories)} categories")


if __name__ == "__main__":
    main()
