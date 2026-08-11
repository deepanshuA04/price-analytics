from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProductRecord:
    sku: str
    title: str
    category: str
    price_excl_tax: float
    price_incl_tax: float
    tax: float
    availability_text: str
    available_count: int | None
    rating: int
    num_reviews: int
    source_url: str


@dataclass(frozen=True)
class PriceObservation:
    sku: str
    collection_date: date
    list_price: float
    current_price: float
    currency: str = "GBP"


@dataclass(frozen=True)
class CollectedItem:
    product: ProductRecord
    price: PriceObservation
