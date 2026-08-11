from __future__ import annotations

import hashlib
import math
import random
from datetime import date

# books.toscrape.com is a static demo catalog: the same price every day. To have
# something worth running moving averages, volatility, and discount-depth SQL
# over, we layer a deterministic, seeded, bounded random walk on top of each
# SKU's real scraped price ("list_price"). Same (sku, date, seed) always produces
# the same price, so re-running a day's collection is idempotent, and the walk is
# reproducible by anyone who clones the repo. This is disclosed in the README —
# it is never presented as real market movement.

DEFAULT_EPOCH = date(2026, 1, 1)
DAILY_SIGMA = 0.015  # daily noise, in log space
MEAN_REVERSION = 0.92  # pulls the drift back toward the list price over time
MIN_LOG_DRIFT = -0.30  # floor: never more than ~26% below list price
MAX_LOG_DRIFT = 0.05  # ceiling: never more than ~5% above list price


def simulate_price(
    list_price: float,
    sku: str,
    collection_date: date,
    seed: int,
    epoch: date = DEFAULT_EPOCH,
) -> float:
    """Deterministic simulated selling price for one SKU on one day.

    A bounded, mean-reverting random walk in log space around `list_price`.
    Deterministic in (list_price, sku, collection_date, seed) — no stored state
    needed, and calling it twice for the same day gives the same price.
    """
    drift = _log_drift(seed, sku, collection_date, epoch)
    return round(list_price * math.exp(drift), 2)


def _log_drift(seed: int, sku: str, collection_date: date, epoch: date) -> float:
    days_elapsed = (collection_date - epoch).days
    if days_elapsed < 0:
        raise ValueError("collection_date is before epoch")

    rng = _sku_rng(seed, sku)
    drift = 0.0
    for _ in range(days_elapsed + 1):
        drift = MEAN_REVERSION * drift + rng.gauss(0.0, DAILY_SIGMA)
        drift = min(max(drift, MIN_LOG_DRIFT), MAX_LOG_DRIFT)
    return drift


def _sku_rng(seed: int, sku: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{sku}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))
