DROP VIEW IF EXISTS v_sku_daily_metrics;

-- Answers: the single wide table Power BI's SKU-detail page reads from - every
-- per-SKU-per-day metric in one place so no measure logic lives in DAX.
-- Grain: one row per (sku, collection_date). Joins the five metric views above
-- plus the product/category attributes that were current as of that day.
-- Caveat: title/rating reflect the dim_product version current when the row
-- was loaded (see dim_product SCD notes in sql/migrations/002), not
-- necessarily what's live on the source site right now.
CREATE VIEW v_sku_daily_metrics AS
SELECT
    f.sku,
    f.collection_date,
    p.title,
    c.category_name,
    f.list_price,
    f.current_price,
    f.available_count,
    ma.avg_price_7d,
    ma.avg_price_30d,
    ch.day_over_day_change,
    ch.day_over_day_change_pct,
    ch.week_over_week_change,
    ch.week_over_week_change_pct,
    r.category_price_rank,
    r.category_price_percentile,
    r.category_sku_count,
    d.discount_depth,
    d.category_median_price,
    d.premium_to_category_median,
    v.price_volatility_30d
FROM fact_price_daily f
JOIN dim_product p ON p.product_key = f.product_key
JOIN dim_category c ON c.category_key = f.category_key
JOIN v_price_moving_avg ma ON ma.sku = f.sku AND ma.collection_date = f.collection_date
JOIN v_price_change ch ON ch.sku = f.sku AND ch.collection_date = f.collection_date
JOIN v_category_rank r ON r.sku = f.sku AND r.collection_date = f.collection_date
JOIN v_discount_depth d ON d.sku = f.sku AND d.collection_date = f.collection_date
JOIN v_price_volatility v ON v.sku = f.sku AND v.collection_date = f.collection_date;
