# price-analytics

E-commerce price & assortment analytics: a scheduled ETL pipeline, a SQLite star-schema
warehouse, and a Power BI dashboard that surfaces which SKUs are overpriced against their
category.

This is a portfolio project. The numbers in the "Results" section below are measured from
this repo's own collection history, not estimates — if a target is missed, that's reported
here along with why.

## Status

Pipeline (collector → warehouse → quality gates → SQL views) is built, tested, and running
on a daily GitHub Actions cron — see [Results](#results) for real numbers. The one piece
left is the Power BI report itself: the data it needs is already exported, but building the
`.pbix` is a manual step in Power BI Desktop (see [Dashboard](#dashboard)) that hasn't been
done yet, so there are no dashboard screenshots below.

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
Applied fresh on every pipeline run by
[`warehouse/views.py`](src/price_analytics/warehouse/views.py) (views hold no data, so
there's no cost to always re-creating them from what's checked in). Nine views:

| View | Answers | Grain |
| --- | --- | --- |
| `v_price_moving_avg` | 7-/30-day moving average price (`AVG() OVER ROWS BETWEEN`) | sku × date |
| `v_price_change` | day-over-day / week-over-week change (`LAG`) | sku × date |
| `v_category_rank` | price rank + percentile within category (`RANK`, `PERCENT_RANK`) | sku × date |
| `v_discount_depth` | discount depth vs. list price + premium vs. category median (rank-based median CTE) | sku × date |
| `v_price_volatility` | 30-day trailing sample stddev of price | sku × date |
| `v_sku_daily_metrics` | the five views above joined into one wide table | sku × date |
| `v_category_overview` | category daily price index + spread | category × date |
| `v_repricing_shortlist` | SKUs >15% above category median, latest day only | sku (latest day) |
| `v_run_log_status` | dashboard status tile: latest run + reliability % | single row |

Every view has a comment block in its `.sql` file stating what it answers, its grain, and its
caveats. [`tests/test_views.py`](tests/test_views.py) loads a small fixture with prices
chosen so every metric can be checked against a hand-computed expected value, not just a
row count.

## Dashboard

Power BI has no native SQLite connector, so the pipeline exports the four dashboard-facing
views to CSV under `powerbi/data/` on every run
([`export.py`](src/price_analytics/warehouse/export.py)) instead of requiring an ODBC
driver install. Report authoring — the actual 3-page `.pbix` — is a manual step in Power BI
Desktop with no scriptable equivalent; see [`powerbi/README.md`](powerbi/README.md) for the
full build guide (data import, page-by-page visual layout, refresh instructions).

## Data-quality gates

Every load checks: nulls in required columns, price within a plausible range, freshness
(max collection date is today), row-count drift vs. the trailing median (>30% swing flags),
duplicate natural keys, and referential integrity to the dimension tables
([`src/price_analytics/quality/checks.py`](src/price_analytics/quality/checks.py)). A
failing check raises `PipelineFailure`, which fails the process (and so the GitHub Actions
run) loudly instead of silently loading bad data — proven in
[`tests/test_pipeline.py`](tests/test_pipeline.py) by seeding an out-of-range price and
asserting the run fails and `run_log` records it.

## Collection

- Real User-Agent identifying the crawler, rate-limited requests, exponential backoff on
  429/5xx, resumable runs (a partial run can pick back up rather than restarting).
- Raw HTML responses are saved gzipped to `raw/YYYY-MM-DD.jsonl.gz` before parsing (one
  JSON line per fetched page, one file per collection date).
- Price simulation: each SKU gets a seeded random-walk drift applied per collection day, on
  top of the real scraped base price. The seed and drift parameters live in code
  (`src/price_analytics/collector/`) so runs are reproducible.

## GitHub Actions

- `ci.yml` — lint (ruff) + test (pytest) on every push.
- `collect.yml` — runs the pipeline (collect + load + quality gates) once a day on a cron
  schedule, plus `workflow_dispatch` for manual runs. Neither runs on every push.

**Warehouse storage decision:** the SQLite file (`warehouse/price_analytics.db`) is
**committed to the repo**, not published as a workflow artifact or release asset. Artifacts
expire (GitHub's default retention is 90 days, which would silently truncate the collection
history this whole project is measuring), and Power BI Desktop needs a local file path to
connect to — committing means `git pull` always gets the latest data with zero extra setup.
The tradeoff: every daily commit rewrites a binary file, so the repo grows without git's
usual delta-compression benefit. At this project's scale (~360 SKUs/day, well under 1 MB of
new fact data per day) that's a non-issue over a portfolio-length collection window; it
would need reconsidering for a much larger SKU count or a multi-year timeline.

The daily job commits the day's raw layer and warehouse changes even when the quality gates
fail (`if: always()`), specifically so a bad day still shows up honestly in `run_log` instead
of quietly vanishing from the reliability number — the *job* itself still shows red in the
Actions tab, which is the "fail loudly" signal, not silence.

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
3. [x] Warehouse: star schema, idempotent upsert load, duplicate-load test
4. [x] Data-quality gates + `run_log`, proven to fail the run on seeded bad data
5. [x] GitHub Actions daily cron
6. [x] Analytical SQL views + tests against a seeded fixture DB
7. [ ] Power BI model, 3-page dashboard — data export is done (see
       [`powerbi/README.md`](powerbi/README.md)); report authoring itself is a manual,
       GUI-only step and is not yet done
8. [ ] Findings write-up + screenshots + measured numbers — write-up and real measured
       numbers are done (see [Results](#results)/[Findings](#findings)); screenshots are
       blocked on the Power BI report itself (item 7)

## Results

**Collection window: 2026-08-11 only, one day, as of this commit.** The daily cron
(`collect.yml`) started running on this date and will keep extending this window with no
further action needed; the numbers below will be re-measured and updated as history
accumulates. Everything here is read directly from `run_log` / `v_run_log_status` and the
warehouse — nothing is projected or estimated.

- **Assortment collected:** 362 SKUs across the 6 chosen categories — Mystery (32),
  Historical Fiction (26), Sequential Art (75), Fiction (65), Nonfiction (110), Young Adult
  (54). This is the site's real inventory in those categories, not a subsample — the
  original ~5,000-listing target assumed a larger catalog than a scraping-practice site
  actually has (see [Data source](#data-source--terms-of-service)).
- **Load reliability: 100% (5/5 runs)**, per `v_run_log_status.reliability_pct`. Read this
  narrowly: it's 5 pipeline executions (manual test runs plus the first scheduled run), all
  on the same calendar day — a real multi-day reliability track record needs the cron to
  keep running, not more manual runs today. No run has failed a quality gate yet.
- **Repricing shortlist: 139 of 362 SKUs (38.4%)** currently sit more than 15% above their
  category's median price (`v_repricing_shortlist`), comfortably past the original 120-SKU
  target — but see [Findings](#findings) below for why that number needs a caveat before
  it means anything.
- **Idempotency:** verified directly — re-running the same collection date twice leaves
  `fact_price_daily` row counts unchanged (`tests/test_loader.py`,
  `tests/test_pipeline.py`), and the same behavior was confirmed against the live site (a
  same-day rerun served all 362 pages from the raw cache with zero re-fetches).

## Findings

**What the data says:** on the one day collected so far, 139 of 362 SKUs (38%) are priced
more than 15% above their category's median. That clears the shortlist-size target, but the
honest reading is narrower than "38% of the assortment needs repricing."

**Why that number needs a caveat, not a headline:** books.toscrape.com states its own
prices "were randomly assigned and have no real meaning," and this project's simulated
price drift (see [Data source](#data-source--terms-of-service)) starts near zero on a SKU's
first collected day. So on day one, `current_price` ≈ the site's original randomly-assigned
price, and the 38% figure is mostly measuring **how wide the source catalog's list-price
distribution already is within a category** — not a market trend, and not something a
repricing team should act on yet. What this run *does* demonstrate is that the mechanism is
correct end to end: real scraped prices flow through a working star schema, the median and
percentile SQL produce sane, hand-verified numbers (see `tests/test_views.py`), and the
shortlist view correctly surfaces exactly the SKUs the math says it should.

**What should happen next:** let the daily cron run for a few weeks. Once `avg_price_7d`,
`avg_price_30d`, `week_over_week_change`, and `price_volatility_30d` have real history
behind them, the repricing shortlist starts answering a different, more useful question —
not "who has a high price today" but "who has been persistently priced above their
category for weeks," which is the version of this finding worth acting on.

**What this analysis cannot tell you, on any collection window:** no conversion, margin, or
sales-volume data is collected, so nothing here can speak to revenue impact — only to
listed-price positioning relative to category peers. And because day-to-day price
*movement* is simulated rather than observed, this project can demonstrate the analytical
mechanism convincingly but cannot claim to have found a real pricing trend in a live market.
Product identity, category, and the base price each SKU starts from are real scraped data;
the day-over-day movement layered on top is not.

## Scope limits

- No conversion, margin, or sales-volume data is collected. Nothing here can speak to
  revenue impact — only to listed-price positioning relative to category peers.
- Day-to-day price *movement* is simulated (see [Data source & terms of service](#data-source--terms-of-service));
  product identity, category, and base pricing are real scraped data from a demo site, not
  a live retailer, so absolute price levels are not representative of any real market.
- The collection window is currently one day (2026-08-11). Trend-dependent metrics
  (moving averages, week-over-week change, multi-point volatility) exist and are tested
  against synthetic fixtures, but haven't yet had enough real history to say anything
  substantive — re-check [Results](#results) after the cron has run for a while.
