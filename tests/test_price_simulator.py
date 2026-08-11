import math
from datetime import date, timedelta

from price_analytics.collector.price_simulator import (
    DEFAULT_EPOCH,
    MAX_LOG_DRIFT,
    MIN_LOG_DRIFT,
    simulate_price,
)


def test_deterministic_for_same_inputs():
    price_a = simulate_price(45.17, "abc123", date(2026, 3, 1), seed=42)
    price_b = simulate_price(45.17, "abc123", date(2026, 3, 1), seed=42)

    assert price_a == price_b


def test_different_seed_changes_price():
    price_a = simulate_price(45.17, "abc123", date(2026, 3, 1), seed=42)
    price_b = simulate_price(45.17, "abc123", date(2026, 3, 1), seed=99)

    assert price_a != price_b


def test_different_sku_changes_price():
    price_a = simulate_price(45.17, "sku-a", date(2026, 3, 1), seed=42)
    price_b = simulate_price(45.17, "sku-b", date(2026, 3, 1), seed=42)

    assert price_a != price_b


def test_price_stays_within_bounds_over_a_long_window():
    list_price = 50.00
    lower_bound = round(list_price * math.exp(MIN_LOG_DRIFT), 2)
    upper_bound = round(list_price * math.exp(MAX_LOG_DRIFT), 2)

    for offset in range(0, 400, 7):
        collection_date = DEFAULT_EPOCH + timedelta(days=offset)
        price = simulate_price(list_price, "abc123", collection_date, seed=42)
        assert lower_bound - 0.01 <= price <= upper_bound + 0.01


def test_epoch_date_is_valid_and_close_to_list_price():
    price = simulate_price(45.17, "abc123", DEFAULT_EPOCH, seed=42)

    assert 30 <= price <= 50


def test_before_epoch_raises():
    import pytest

    with pytest.raises(ValueError):
        simulate_price(45.17, "abc123", DEFAULT_EPOCH - timedelta(days=1), seed=42)
