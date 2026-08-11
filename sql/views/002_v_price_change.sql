DROP VIEW IF EXISTS v_price_change;

-- Answers: how much has this SKU's price moved since yesterday and since a
-- week ago, in absolute and percentage terms.
-- Grain: one row per (sku, collection_date).
-- Caveat: LAG compares to the SKU's *previous collected row*, not strictly a
-- calendar day - if a SKU is missing from a day's run, the comparison silently
-- skips to the last day it was actually seen.
CREATE VIEW v_price_change AS
SELECT
    sku,
    collection_date,
    current_price,
    LAG(current_price, 1) OVER (PARTITION BY sku ORDER BY collection_date) AS prior_day_price,
    current_price
        - LAG(current_price, 1) OVER (PARTITION BY sku ORDER BY collection_date)
        AS day_over_day_change,
    ROUND(
        100.0 * (
            current_price
            - LAG(current_price, 1) OVER (PARTITION BY sku ORDER BY collection_date)
        ) / NULLIF(LAG(current_price, 1) OVER (PARTITION BY sku ORDER BY collection_date), 0),
        2
    ) AS day_over_day_change_pct,
    LAG(current_price, 7) OVER (PARTITION BY sku ORDER BY collection_date) AS prior_week_price,
    current_price
        - LAG(current_price, 7) OVER (PARTITION BY sku ORDER BY collection_date)
        AS week_over_week_change,
    ROUND(
        100.0 * (
            current_price
            - LAG(current_price, 7) OVER (PARTITION BY sku ORDER BY collection_date)
        ) / NULLIF(LAG(current_price, 7) OVER (PARTITION BY sku ORDER BY collection_date), 0),
        2
    ) AS week_over_week_change_pct
FROM fact_price_daily;
