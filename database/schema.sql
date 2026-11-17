-- E-commerce Database Schema (REFERENCE ONLY)
--
-- The canonical schema lives in code: scripts/upload_to_db.py (SQLAlchemy Core
-- `products` Table + Index definitions, created with metadata.create_all(), and
-- per-dialect views). The pipeline never executes this file. Keep it in sync
-- with the code when the schema changes. Syntax below is SQLite.

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) NOT NULL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    stock INTEGER NOT NULL,
    supplier VARCHAR(255),
    last_updated DATE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_supplier ON products(supplier);
CREATE INDEX IF NOT EXISTS idx_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_stock ON products(stock);

-- Views (PostgreSQL/MySQL use CREATE OR REPLACE VIEW instead of IF NOT EXISTS)
CREATE VIEW IF NOT EXISTS low_stock_products AS
SELECT product_id, product_name, category, stock
FROM products
WHERE stock < 10;

CREATE VIEW IF NOT EXISTS products_by_category AS
SELECT category, COUNT(*) AS product_count, AVG(price) AS avg_price,
       SUM(stock) AS total_stock
FROM products
GROUP BY category;

CREATE VIEW IF NOT EXISTS supplier_statistics AS
SELECT supplier, COUNT(*) AS product_count, AVG(price) AS avg_price,
       MIN(price) AS min_price, MAX(price) AS max_price
FROM products
WHERE supplier IS NOT NULL
GROUP BY supplier;
