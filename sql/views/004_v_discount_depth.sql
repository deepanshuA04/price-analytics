DROP VIEW IF EXISTS v_discount_depth;

-- Answers: how deep a discount each SKU is carrying against its own list
-- price, and where its current price sits against the category's median
-- selling price that day.
-- Grain: one row per (sku, collection_date).
-- Caveat: "list_price" is the scraped source price, treated here as a fixed
-- reference point per SKU (see README > Data source) - not a claim about
-- anyone's real MSRP/list pricing strategy. category_median_price uses a
-- rank-based median CTE (handles even/odd counts by averaging the two middle
-- ranks), not NTILE.
CREATE VIEW v_discount_depth AS
WITH ranked AS (
    SELECT
        category_key,
        collection_date,
        current_price,
        ROW_NUMBER() OVER (
            PARTITION BY category_key, collection_date ORDER BY current_price
        ) AS rn,
        COUNT(*) OVER (PARTITION BY category_key, collection_date) AS cnt
    FROM fact_price_daily
),
category_median AS (
    SELECT category_key, collection_date, AVG(current_price) AS category_median_price
    FROM ranked
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
    GROUP BY category_key, collection_date
)
SELECT
    f.sku,
    f.collection_date,
    c.category_name,
    f.list_price,
    f.current_price,
    ROUND((f.list_price - f.current_price) / NULLIF(f.list_price, 0), 4) AS discount_depth,
    m.category_median_price,
    ROUND(
        (f.current_price - m.category_median_price) / NULLIF(m.category_median_price, 0), 4
    ) AS premium_to_category_median
FROM fact_price_daily f
JOIN dim_category c ON c.category_key = f.category_key
JOIN category_median m
    ON m.category_key = f.category_key AND m.collection_date = f.collection_date;
