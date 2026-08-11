DROP VIEW IF EXISTS v_repricing_shortlist;

-- Answers: which SKUs, as of the most recent collection day, are priced more
-- than 15% above their category's median selling price - the repricing
-- shortlist page's source, sortable by gap.
-- Grain: one row per SKU, for the single most recent collection_date only
-- (a point-in-time shortlist, not a daily time series).
-- Caveat: 15% is a fixed threshold chosen for this project, not derived from
-- any margin or elasticity data - see README > Scope limits.
CREATE VIEW v_repricing_shortlist AS
SELECT
    sku,
    collection_date,
    title,
    category_name,
    current_price,
    category_median_price,
    premium_to_category_median,
    category_price_rank,
    category_sku_count
FROM v_sku_daily_metrics
WHERE collection_date = (SELECT MAX(collection_date) FROM fact_price_daily)
  AND premium_to_category_median > 0.15
ORDER BY premium_to_category_median DESC;
