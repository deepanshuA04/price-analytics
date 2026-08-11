DROP VIEW IF EXISTS v_price_volatility;

-- Answers: how much has this SKU's price been bouncing around lately - the
-- sample standard deviation of daily price over the trailing 30 collected days.
-- Grain: one row per (sku, collection_date).
-- Caveat: SQLite has no built-in STDDEV, so this derives population variance
-- from AVG(x^2) - AVG(x)^2 and rescales by n/(n-1) for the sample estimate;
-- NULL until a SKU has at least 2 collected days, and the first 29 days of a
-- SKU's history have a shorter-than-30-day window.
CREATE VIEW v_price_volatility AS
WITH windowed AS (
    SELECT
        sku,
        collection_date,
        AVG(current_price) OVER w AS avg_price,
        AVG(current_price * current_price) OVER w AS avg_sq_price,
        COUNT(*) OVER w AS n_days
    FROM fact_price_daily
    WINDOW w AS (
        PARTITION BY sku ORDER BY collection_date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    )
)
SELECT
    sku,
    collection_date,
    n_days,
    CASE
        WHEN n_days > 1 THEN
            ROUND(
                SQRT(MAX(avg_sq_price - avg_price * avg_price, 0.0) * n_days / (n_days - 1)),
                4
            )
        ELSE NULL
    END AS price_volatility_30d
FROM windowed;
