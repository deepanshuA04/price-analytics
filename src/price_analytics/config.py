from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Six categories chosen for decent assortment size (roughly 30-110 books each,
# ~360 SKUs total) rather than the site's smallest categories.
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "mystery_3",
    "historical-fiction_4",
    "sequential-art_5",
    "fiction_10",
    "nonfiction_13",
    "young-adult_21",
)


@dataclass(frozen=True)
class Settings:
    base_url: str
    user_agent: str
    request_delay_seconds: float
    max_retries: int
    price_drift_seed: int
    raw_dir: Path
    categories: tuple[str, ...] = field(default_factory=lambda: DEFAULT_CATEGORIES)


def load_settings() -> Settings:
    return Settings(
        base_url=os.environ.get("COLLECTOR_BASE_URL", "https://books.toscrape.com"),
        user_agent=os.environ.get(
            "COLLECTOR_USER_AGENT",
            "price-analytics-bot/0.1 (+https://github.com/deepanshuA04/price-analytics)",
        ),
        request_delay_seconds=float(os.environ.get("COLLECTOR_REQUEST_DELAY_SECONDS", "1.0")),
        max_retries=int(os.environ.get("COLLECTOR_MAX_RETRIES", "5")),
        price_drift_seed=int(os.environ.get("PRICE_DRIFT_SEED", "20260811")),
        raw_dir=Path(os.environ.get("COLLECTOR_RAW_DIR", str(REPO_ROOT / "raw"))),
    )
