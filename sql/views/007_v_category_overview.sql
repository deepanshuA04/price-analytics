DROP VIEW IF EXISTS v_category_overview;

-- Answers: category-level daily price index and spread - the "market
-- overview" dashboard page's primary source. The index equals 100 on the
-- first day a category appears in the warehouse, so categories with very
-- different absolute price levels are still comparable as trend lines.
-- Grain: one row per (category, collection_date).
-- Caveat: the index base is the first *collected* day for that category in
-- this warehouse, not any external baseline - it measures relative movement
-- since collection started, nothing more.
CREATE VIEW v_category_overview AS
WITH daily AS (
    SELECT
        c.category_key,
        c.category_name,
        f.collection_date,
        COUNT(*) AS sku_count,
        AVG(f.current_price) AS avg_price,
        MIN(f.current_price) AS min_price,
        MAX(f.current_price) AS max_price
    FROM fact_price_daily f
    JOIN dim_category c ON c.category_key = f.category_key
    GROUP BY c.category_key, c.category_name, f.collection_date
),
base AS (
    SELECT category_key, MIN(collection_date) AS base_date
    FROM daily
    GROUP BY category_key
)
SELECT
    d.category_key,
    d.category_name,
    d.collection_date,
    d.sku_count,
    ROUND(d.avg_price, 2) AS avg_price,
    ROUND(d.min_price, 2) AS min_price,
    ROUND(d.max_price, 2) AS max_price,
    ROUND(d.max_price - d.min_price, 2) AS price_spread,
    ROUND(100.0 * d.avg_price / NULLIF(base_price.avg_price, 0), 2) AS price_index
FROM daily d
JOIN base ON base.category_key = d.category_key
JOIN daily base_price
    ON base_price.category_key = d.category_key AND base_price.collection_date = base.base_date;
