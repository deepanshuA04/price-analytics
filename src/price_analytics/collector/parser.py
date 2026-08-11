from __future__ import annotations

import re

from bs4 import BeautifulSoup

from price_analytics.collector.records import ProductRecord

RATING_WORDS = {"Zero": 0, "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
_AVAILABLE_COUNT_RE = re.compile(r"\((\d+)\s+available\)")
_NUMERIC_RE = re.compile(r"[0-9]+\.?[0-9]*")


def parse_category_page(html: str) -> tuple[list[str], str | None]:
    """Returns (product detail hrefs as found in the markup, next-page href or None).

    Hrefs are relative to the page they were found on — the caller resolves them
    with `urljoin(page_url, href)`, since this function doesn't know the page's URL.
    """
    soup = BeautifulSoup(html, "lxml")
    hrefs = [a["href"] for a in soup.select("article.product_pod h3 a")]
    next_link = soup.select_one("li.next a")
    next_href = next_link["href"] if next_link else None
    return hrefs, next_href


def parse_product_page(html: str, source_url: str) -> ProductRecord:
    soup = BeautifulSoup(html, "lxml")

    info = {
        row.find("th").get_text(strip=True): row.find("td").get_text(strip=True)
        for row in soup.select("table.table.table-striped tr")
    }

    title = soup.select_one("div.product_main h1").get_text(strip=True)

    breadcrumb_links = soup.select("ul.breadcrumb li a")
    category = breadcrumb_links[-1].get_text(strip=True) if breadcrumb_links else "Unknown"

    rating_tag = soup.select_one("p.star-rating")
    rating_word = next(
        (c for c in (rating_tag.get("class") or []) if c != "star-rating"), None
    )
    rating = RATING_WORDS.get(rating_word, 0)

    availability_text = info.get("Availability", "")
    available_match = _AVAILABLE_COUNT_RE.search(availability_text)
    available_count = int(available_match.group(1)) if available_match else None

    return ProductRecord(
        sku=info["UPC"],
        title=title,
        category=category,
        price_excl_tax=_parse_money(info["Price (excl. tax)"]),
        price_incl_tax=_parse_money(info["Price (incl. tax)"]),
        tax=_parse_money(info["Tax"]),
        availability_text=availability_text,
        available_count=available_count,
        rating=rating,
        num_reviews=int(info.get("Number of reviews", 0)),
        source_url=source_url,
    )


def _parse_money(text: str) -> float:
    match = _NUMERIC_RE.search(text)
    if not match:
        raise ValueError(f"could not parse a price out of {text!r}")
    return float(match.group())
