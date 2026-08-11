# Power BI dashboard — build guide

This is the one piece of the project that has to be done by hand in the Power BI
Desktop GUI — there's no supported, scriptable way to author report pages and visuals
(Tabular Editor + TMDL can script the *data model*, but not the report layer). Everything
up to this point (the data, the metric definitions, the export) is already automated and
checked in; this guide is the shortest path through the manual part.

## Why CSV import instead of a live SQLite connection

Power BI Desktop has no native SQLite connector. The realistic options are a third-party
ODBC driver (needs installing and configuring a DSN — a real setup cost, and a dependency
on an unmaintained community driver) or a Python-script data source (needs Power BI's
Python integration pointed at this project's `.venv`, another one-time config step). Both
work, but both add friction for zero benefit at this project's scale.

Instead, [`src/price_analytics/warehouse/export.py`](../src/price_analytics/warehouse/export.py)
snapshots the four dashboard-facing views to CSV under `powerbi/data/` on every pipeline
run (see `export_views_to_csv`, called from `run_pipeline`). Power BI imports those CSVs
directly — no driver, no DSN, no Python config. The tradeoff: refreshing the dashboard
means re-running the pipeline (or `uv run python -c "from price_analytics.warehouse.export
import export_views_to_csv; ..."` against the existing warehouse) and then hitting
**Refresh** in Power BI, rather than a fully live connection. For a project that updates
once a day via cron, that's a non-issue.

## 1. Install Power BI Desktop

Free, from the Microsoft Store or [powerbi.microsoft.com/desktop](https://powerbi.microsoft.com/desktop/).
Not currently installed on this machine, so this is step zero.

## 2. Import the data

1. Open Power BI Desktop → **Get Data** → **Text/CSV**.
2. Import all four files from `powerbi/data/`:
   - `v_sku_daily_metrics.csv`
   - `v_category_overview.csv`
   - `v_repricing_shortlist.csv`
   - `v_run_log_status.csv`
3. **Load** each one (no transforms needed — the views already did the shaping). Power BI
   will infer types; double check `collection_date` comes in as a Date, not Text (Power
   Query → right-click the column → Change Type → Date if it doesn't auto-detect).
4. No relationships needed between the four tables — each page below reads from exactly
   one of them, by design, so there's nothing to join and nothing to get wrong.

## 3. Page 1 — Market overview

Source: `v_category_overview` (category × date) and `v_run_log_status` (single row).

- **Status tile** (top of page): three cards from `v_run_log_status` — `latest_run_status`,
  `latest_run_date`, `reliability_pct`. Conditionally format the status card (green on
  "success", red on "failed") — Format pane → Conditional formatting → Background color,
  rule based on field value.
- **Category price index over time**: line chart, X = `collection_date`, Y = `price_index`,
  Legend = `category_name`. This is the headline "is the market moving" chart — index
  starts at 100 for every category on the day it entered the warehouse (see the view's
  comment block for why), so categories are comparable despite very different absolute
  price levels.
- **Category spread**: bar chart, X = `category_name`, Y = `price_spread` (or `avg_price`),
  for the latest `collection_date` — use a filter/slicer on `collection_date` set to the max
  date, or add a "latest date" measure if you want it to auto-track.
- **Assortment size**: card or bar chart on `sku_count` by `category_name`.

## 4. Page 2 — SKU detail

Source: `v_sku_daily_metrics` (sku × date).

- **SKU picker**: a slicer on `title` (searchable dropdown) so the page focuses on one book
  at a time.
- **Price history**: line chart, X = `collection_date`, Y = three measures on the same
  chart — `current_price`, `avg_price_7d`, `avg_price_30d` — so the moving averages visibly
  smooth the raw line.
- **KPI cards**: `price_volatility_30d`, `category_price_rank`, `category_price_percentile`,
  `day_over_day_change_pct` — all filtered to the selected SKU's latest row (use a table
  visual sorted by `collection_date` descending with "Show top 1", or a measure wrapped in
  `LASTNONBLANK`/`MAX` if you're comfortable with a little DAX; the metric itself is still
  defined in SQL, this is just picking out the latest row for display).
- **Recent history table**: `collection_date`, `current_price`, `discount_depth`,
  `category_price_rank` for the selected SKU, sorted newest first.

## 5. Page 3 — Repricing shortlist

Source: `v_repricing_shortlist` (already filtered to the latest day and >15% premium — no
extra filtering needed on this page).

- **Table**: `title`, `category_name`, `current_price`, `category_median_price`,
  `premium_to_category_median` (format as %), `category_price_rank`. Sort by
  `premium_to_category_median` descending — that's the "worst offenders first" view.
- **Category slicer**: filter the table by `category_name`.
- **Card**: `COUNTROWS(v_repricing_shortlist)` — the shortlist size, the number this
  project's resume bullet is actually about. Report the real number here, not a target.
- **Bar chart**: top 20 by `premium_to_category_median`, X = `title` (or `sku` if titles are
  too long to read), Y = `premium_to_category_median`.

## 6. Save, screenshot, document

1. Save as `powerbi/price_analytics.pbix`.
2. Screenshot each of the three pages.
3. Add the screenshots to the main [`README.md`](../README.md) Findings section, along
   with the real numbers you see on the status tile and the shortlist count — not the
   placeholder numbers from the original project brief.

## Refreshing later

```bash
uv run python -m price_analytics.pipeline   # collects the day, reloads the warehouse,
                                              # and re-exports powerbi/data/*.csv
```
Then in Power BI Desktop: **Home → Refresh**.
