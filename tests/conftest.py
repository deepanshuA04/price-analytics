from __future__ import annotations

from datetime import date

import pytest

from price_analytics.collector.records import CollectedItem, PriceObservation, ProductRecord
from price_analytics.warehouse.db import connect
from price_analytics.warehouse.migrate import migrate


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_path):
    connection = connect(db_path)
    migrate(connection)
    yield connection
    connection.close()


def make_item(
    sku: str = "sku-1",
    title: str = "Test Book",
    category: str = "Fiction",
    list_price: float = 10.0,
    current_price: float = 9.0,
    collection_date: date = date(2026, 3, 1),
    available_count: int = 5,
    rating: int = 3,
) -> CollectedItem:
    product = ProductRecord(
        sku=sku,
        title=title,
        category=category,
        price_excl_tax=list_price,
        price_incl_tax=list_price,
        tax=0.0,
        availability_text=f"In stock ({available_count} available)",
        available_count=available_count,
        rating=rating,
        num_reviews=0,
        source_url=f"https://example.test/{sku}",
    )
    price = PriceObservation(
        sku=sku,
        collection_date=collection_date,
        list_price=list_price,
        current_price=current_price,
    )
    return CollectedItem(product=product, price=price)
