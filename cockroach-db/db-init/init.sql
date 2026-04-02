-- Initialization script for Store Manager with CockroachDB

CREATE DATABASE IF NOT EXISTS labo09;
USE labo09;

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS stocks CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Users table
CREATE TABLE users (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100)  NOT NULL,
    email      VARCHAR(150)  NOT NULL UNIQUE,
    created_at TIMESTAMPTZ   DEFAULT now()
);

-- Products table
CREATE TABLE products (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(150)    NOT NULL,
    sku        VARCHAR(64)     NOT NULL UNIQUE,
    price      DECIMAL(10,2)   NOT NULL,
    created_at TIMESTAMPTZ     DEFAULT now()
);

-- Orders table
CREATE TABLE orders (
    id             SERIAL PRIMARY KEY,
    user_id        INT             NOT NULL,
    total_amount   DECIMAL(12,2)   NOT NULL DEFAULT 0,
    payment_link   VARCHAR(100),
    is_paid        BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ     DEFAULT now(),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Order items
CREATE TABLE order_items (
    id           SERIAL PRIMARY KEY,
    order_id     INT             NOT NULL,
    product_id   INT             NOT NULL,
    quantity     INT             NOT NULL DEFAULT 1,
    unit_price   DECIMAL(10,2)   NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(id)   ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Product stocks (with version column for optimistic locking)
CREATE TABLE stocks (
    product_id  INT PRIMARY KEY,
    quantity    INT NOT NULL DEFAULT 0,
    version     INT NOT NULL DEFAULT 0,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Mock data: users
INSERT INTO users (id, name, email) VALUES
(1, 'Ada Lovelace',   'alovelace@example.com'),
(2, 'Adele Goldberg', 'agoldberg@example.com'),
(3, 'Alan Turing',    'aturing@example.com');

-- Mock data: products
INSERT INTO products (id, name, sku, price) VALUES
(1, 'Laptop ABC',          'LP12567', 1999.99),
(2, 'Keyboard DEF',        'KB67890',   59.50),
(3, 'Gadget XYZ',          'GG12345',    5.75),
(4, '27-inch Screen WYZ',  'SC27289',  299.75);

-- Mock data: product stocks
INSERT INTO stocks (product_id, quantity) VALUES
(1, 1000),
(2,  500),
(3,    2),
(4,   90);

-- Indexes
CREATE INDEX idx_stocks_product_id      ON stocks      (product_id);
CREATE INDEX idx_order_items_product_id ON order_items (product_id);
CREATE INDEX idx_orders_user_id         ON orders      (user_id);
CREATE INDEX idx_orders_is_paid         ON orders      (is_paid);
