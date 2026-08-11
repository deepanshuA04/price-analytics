DROP VIEW IF EXISTS v_price_moving_avg;

-- Answers: what has this SKU's price actually been doing lately, smoothed over
-- 7- and 30-day windows so a single noisy day doesn't read as a trend.
-- Grain: one row per (sku, collection_date).
-- Caveat: the first 6/29 days of any SKU's history have a shorter window (fewer
-- than 7/30 prior rows exist yet), so early moving averages are less stable.
CREATE VIEW v_price_moving_avg AS
SELECT
    sku,
    collection_date,
    current_price,
    AVG(current_price) OVER (
        PARTITION BY sku ORDER BY collection_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS avg_price_7d,
    AVG(current_price) OVER (
        PARTITION BY sku ORDER BY collection_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS avg_price_30d,
    COUNT(*) OVER (
        PARTITION BY sku ORDER BY collection_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS days_in_30d_window
FROM fact_price_daily;
