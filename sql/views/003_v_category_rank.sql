DROP VIEW IF EXISTS v_category_rank;

-- Answers: how expensive is this SKU relative to others in the same category
-- on the same day - its rank (1 = most expensive) and percentile.
-- Grain: one row per (sku, collection_date).
-- Caveat: RANK() leaves gaps after ties (two SKUs tied for 1st -> next rank is
-- 3rd); PERCENT_RANK() is 0 for the cheapest SKU in the category that day and
-- is undefined in any meaningful sense when category_sku_count is 1.
CREATE VIEW v_category_rank AS
SELECT
    f.sku,
    f.collection_date,
    c.category_name,
    f.current_price,
    RANK() OVER (
        PARTITION BY f.category_key, f.collection_date ORDER BY f.current_price DESC
    ) AS category_price_rank,
    ROUND(
        PERCENT_RANK() OVER (
            PARTITION BY f.category_key, f.collection_date ORDER BY f.current_price
        ),
        4
    ) AS category_price_percentile,
    COUNT(*) OVER (PARTITION BY f.category_key, f.collection_date) AS category_sku_count
FROM fact_price_daily f
JOIN dim_category c ON c.category_key = f.category_key;
