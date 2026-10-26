-- Run this once:  mysql -u root -p < schema.sql
CREATE DATABASE IF NOT EXISTS shop_db;
USE shop_db;

CREATE TABLE IF NOT EXISTS products (
    id       INT AUTO_INCREMENT PRIMARY KEY,
    name     VARCHAR(100)  NOT NULL,
    category VARCHAR(50)   NOT NULL,
    price    DECIMAL(10,2) NOT NULL CHECK (price >= 0),
    stock    INT           NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100)  NOT NULL,
    total         DECIMAL(10,2) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id   INT           NOT NULL,
    product_id INT           NOT NULL,
    quantity   INT           NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Sample data (only inserted if the table is empty)
INSERT INTO products (name, category, price, stock)
SELECT * FROM (
    SELECT 'Wireless Mouse'      AS name, 'Electronics' AS category, 699.00  AS price, 25 AS stock UNION ALL
    SELECT 'Mechanical Keyboard', 'Electronics', 2499.00, 15 UNION ALL
    SELECT 'USB-C Charger 65W',   'Electronics', 1299.00, 30 UNION ALL
    SELECT 'Bluetooth Speaker',   'Electronics', 1799.00, 12 UNION ALL
    SELECT 'Cotton T-Shirt',      'Clothing',     499.00, 50 UNION ALL
    SELECT 'Denim Jeans',         'Clothing',    1499.00, 20 UNION ALL
    SELECT 'Running Shoes',       'Clothing',    2999.00, 10 UNION ALL
    SELECT 'Python Crash Course', 'Books',        899.00, 18 UNION ALL
    SELECT 'Clean Code',          'Books',        999.00,  8 UNION ALL
    SELECT 'Notebook (Pack of 5)','Stationery',   349.00, 40 UNION ALL
    SELECT 'Gel Pen Set',         'Stationery',   199.00, 60
) AS seed
WHERE NOT EXISTS (SELECT 1 FROM products);
