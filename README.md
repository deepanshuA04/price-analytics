# price-analytics

E-commerce price & assortment analytics: a scheduled ETL pipeline, a SQLite star-schema
warehouse, and a Power BI dashboard that surfaces which SKUs are overpriced against their
category.

This is a portfolio project. The numbers in the "Results" section below are measured from
this repo's own collection history, not estimates — if a target is missed, that's reported
here along with why.

## Status

Early build. Collector and warehouse are in progress; see [Build order](#build-order) below.
There is no dashboard or results yet.

## Data source & terms of service

**Source:** [books.toscrape.com](https://books.toscrape.com), a static demo storefront
built by [Zyte](https://www.zyte.com/) specifically for scraping practice.

**Decision, checked 2026-08-11:**
- `robots.txt` returns HTTP 404 — no robots file exists, so there is no machine-readable
  restriction to honor.
- The homepage states outright: *"We love being scraped!"* and *"This is a demo website
  for web scraping purposes. Prices and ratings here were randomly assigned and have no
  real meaning."*
- There is no ToS page and no rate-limit or scraping policy published anywhere on the site.

This is about as close to an explicit invitation to scrape as a site can give, so it was
chosen over a real retailer where scraping would be legally and ethically murkier. The
collector still rate-limits and backs off (see [Collection](#collection)) as a matter of
politeness, not because the site requires it.

**Known limitation — prices are static.** books.toscrape.com is a fixed demo dataset: the
same ~1,000 books at the same prices every day, across 50 categories. A price-analytics
project needs prices that actually move, so this pipeline layers a small, clearly-labeled
**simulated daily price drift** on top of the real scraped listings (see
[Collection](#collection)). Every price in the warehouse is traceable to either "scraped
as-is" or "scraped + simulated drift" — this is stated plainly here and again in the
Findings section so it's never presented as real market data. Product titles, authors,
categories, star ratings, and availability text are all real scraped values; only the
day-to-day price movement is synthetic.

Because of this, the collector targets **6 of the site's 50 categories**, not "~5,000
listings" — the site's entire catalog is ~1,000 books. The category count and row volume
actually collected are reported in [Results](#results) once the pipeline has run.

## Architecture

```
collector (httpx + BeautifulSoup)
  -> raw/ (gzipped HTML, one file per run, append-only)
    -> parser -> price simulator (seeded per-SKU random walk)
      -> SQLite warehouse (star schema, idempotent upsert)
        -> sql/views/*.sql (moving averages, rank, discount depth, volatility)
          -> Power BI dashboard
```

Raw HTML lands in `raw/` before any parsing happens, so a parser bug can be fixed and
replayed against history without re-fetching the site.

## Warehouse

SQLite, star schema:

- `dim_product` — one row per SKU, slowly-changing (title/category changes are kept as
  history, not overwritten)
- `dim_category`
- `dim_date`
- `fact_price_daily` — **grain: one row per SKU per collection date.** Idempotent upsert on
  `(sku, collection_date)`; re-running the same day's collection does not duplicate rows.
- `run_log` — one row per pipeline run (timestamp, rows in/loaded/rejected, checks
  passed/failed, duration). The dashboard's status tile and the reliability number in
  [Results](#results) are computed from this table, not estimated.

## Analytical SQL layer

Versioned views in [`sql/views/`](sql/views/) are the single definition of every metric the
dashboard shows — Power BI reads views, not raw tables, and DAX does presentation only.
Covers 7/30-day moving average price, day-over-day and week-over-week change, category
rank/percentile, discount depth, category median, and 30-day price volatility. Not yet
written — tracked in [Build order](#build-order).

## Data-quality gates

Every load checks: nulls in required columns, price within a plausible range, freshness
(max collection date is today), row-count drift vs. the trailing median (>30% swing flags),
duplicate natural keys, and referential integrity to the dimension tables. A failing check
fails the GitHub Actions run. Not yet implemented — tracked in [Build order](#build-order).

## Collection

- Real User-Agent identifying the crawler, rate-limited requests, exponential backoff on
  429/5xx, resumable runs (a partial run can pick back up rather than restarting).
- Raw HTML responses are saved gzipped to `raw/YYYY-MM-DD/` before parsing.
- Price simulation: each SKU gets a seeded random-walk drift applied per collection day, on
  top of the real scraped base price. The seed and drift parameters live in code
  (`src/price_analytics/collector/`) so runs are reproducible.

## GitHub Actions

- `ci.yml` — lint (ruff) + test (pytest) on every push.
- A scheduled collection workflow will be added once the collector and warehouse are
  built (see [Build order](#build-order)); it runs on a daily cron, not on every push.

## Local development

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
```

Requires Python 3.12 (pinned in `pyproject.toml`) and [uv](https://docs.astral.sh/uv/).

## Build order

1. [x] Scaffold + CI skeleton + data source/ToS decision
2. [x] Collector: polite fetching, raw layer, resumable runs, parser unit tests
3. [ ] Warehouse: star schema, idempotent upsert load, duplicate-load test
4. [ ] Data-quality gates + `run_log`, proven to fail the run on seeded bad data
5. [ ] GitHub Actions daily cron
6. [ ] Analytical SQL views + tests against a seeded fixture DB
7. [ ] Power BI model, 3-page dashboard
8. [ ] Findings write-up + screenshots + measured numbers

## Results

Not yet available in full — the pipeline has no collection history in a warehouse yet
(that's the next milestone). What's confirmed so far: the collector's first live run
(2026-08-11) pulled **362 products across the 6 chosen categories** (mystery, historical
fiction, sequential art, fiction, nonfiction, young adult), and a same-day rerun served
all 362 from the raw layer with zero re-fetches. Load reliability, moving averages, and
the repricing shortlist need the warehouse and a real collection window, so those numbers
land in later commits.

## Findings

Not yet available.

## Scope limits

- No conversion, margin, or sales-volume data is collected. Nothing here can speak to
  revenue impact — only to listed-price positioning relative to category peers.
- Day-to-day price *movement* is simulated (see [Data source & terms of service](#data-source--terms-of-service));
  product identity, category, and base pricing are real scraped data from a demo site, not
  a live retailer, so absolute price levels are not representative of any real market.
