-- Grain: one row per SKU per collection date. Natural key (sku, collection_date)
-- is the primary key, so re-loading a day's data is an upsert, not an insert.
CREATE TABLE fact_price_daily (
    sku TEXT NOT NULL,
    collection_date TEXT NOT NULL REFERENCES dim_date (date_key),
    product_key INTEGER NOT NULL REFERENCES dim_product (product_key),
    category_key INTEGER NOT NULL REFERENCES dim_category (category_key),
    list_price REAL NOT NULL,
    current_price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'GBP',
    available_count INTEGER,
    loaded_at TEXT NOT NULL,
    PRIMARY KEY (sku, collection_date)
);

CREATE INDEX idx_fact_price_daily_date ON fact_price_daily (collection_date);
CREATE INDEX idx_fact_price_daily_category_date ON fact_price_daily (category_key, collection_date);
