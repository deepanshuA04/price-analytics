from pathlib import Path

from price_analytics.collector.parser import parse_category_page, parse_product_page

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_category_page_with_next_page():
    hrefs, next_href = parse_category_page(_read("category_page_with_next.html"))

    assert len(hrefs) == 20
    assert hrefs[0] == "../../../sharp-objects_997/index.html"
    assert next_href == "page-2.html"


def test_parse_category_page_last_page_has_no_next():
    hrefs, next_href = parse_category_page(_read("category_page_last_page.html"))

    assert len(hrefs) == 11
    assert next_href is None


def test_parse_product_page():
    product = parse_product_page(
        _read("product_page.html"),
        source_url="https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
    )

    assert product.sku == "a22124811bfa8350"
    assert product.title == "It's Only the Himalayas"
    assert product.category == "Travel"
    assert product.price_excl_tax == 45.17
    assert product.price_incl_tax == 45.17
    assert product.tax == 0.00
    assert product.availability_text == "In stock (19 available)"
    assert product.available_count == 19
    assert product.rating == 2
    assert product.num_reviews == 0
    assert product.source_url.endswith("its-only-the-himalayas_981/index.html")
