-- E-commerce Database Schema
-- Products Table for storing product information

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    stock INT NOT NULL,
    supplier VARCHAR(255),
    last_updated DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_supplier ON products(supplier);
CREATE INDEX IF NOT EXISTS idx_price ON products(price);
CREATE INDEX IF NOT EXISTS idx_stock ON products(stock);

-- View for products with low stock
CREATE VIEW IF NOT EXISTS low_stock_products AS
SELECT
    product_id,
    product_name,
    category,
    stock
FROM products
WHERE stock < 10
ORDER BY stock ASC;

-- View for products by category
CREATE VIEW IF NOT EXISTS products_by_category AS
SELECT
    category,
    COUNT(*) as product_count,
    AVG(price) as avg_price,
    SUM(stock) as total_stock
FROM products
GROUP BY category
ORDER BY product_count DESC;

-- View for supplier statistics
CREATE VIEW IF NOT EXISTS supplier_statistics AS
SELECT
    supplier,
    COUNT(*) as product_count,
    AVG(price) as avg_price,
    MIN(price) as min_price,
    MAX(price) as max_price
FROM products
WHERE supplier IS NOT NULL
GROUP BY supplier
ORDER BY product_count DESC;
