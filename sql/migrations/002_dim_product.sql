-- Slowly-changing product attributes (type 2): a new row is inserted whenever
-- title or category changes for a SKU, rather than overwriting history.
-- is_current=1 identifies the row that applies as of the latest load.
CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL,
    title TEXT NOT NULL,
    category_key INTEGER NOT NULL REFERENCES dim_category (category_key),
    rating INTEGER,
    source_url TEXT,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    is_current INTEGER NOT NULL DEFAULT 1,
    UNIQUE (sku, valid_from)
);

CREATE INDEX idx_dim_product_sku_current ON dim_product (sku, is_current);
