-- FoodWasteZero  |  MySQL / MariaDB (XAMPP) schema
-- Import in phpMyAdmin (Import tab) or run:  python setup_db.py

CREATE DATABASE IF NOT EXISTS foodwastezero CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE foodwastezero;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS donations, waste_log, actions, sales, batches, partners, products, categories, users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100) NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE categories (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    name      VARCHAR(60) NOT NULL UNIQUE,
    donatable TINYINT(1)  NOT NULL DEFAULT 1   -- can surplus of this category be safely donated?
) ENGINE=InnoDB;

CREATE TABLE products (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    sku             VARCHAR(30)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    category_id     INT NOT NULL,
    unit            VARCHAR(20)  NOT NULL DEFAULT 'pc',
    unit_cost       DECIMAL(10,2) NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    kg_per_unit     DECIMAL(6,3)  NOT NULL DEFAULT 0.500,
    shelf_life_days INT NOT NULL DEFAULT 7,
    active          TINYINT(1) NOT NULL DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES categories(id)
) ENGINE=InnoDB;

CREATE TABLE batches (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    product_id    INT NOT NULL,
    batch_code    VARCHAR(40) NOT NULL,
    qty_received  INT NOT NULL,
    qty_remaining INT NOT NULL,
    received_on   DATE NOT NULL,
    expires_on    DATE NOT NULL,
    discount_pct  DECIMAL(5,2) NOT NULL DEFAULT 0,   -- markdown currently applied to this batch
    FOREIGN KEY (product_id) REFERENCES products(id),
    INDEX idx_batches_expiry (expires_on),
    INDEX idx_batches_product (product_id)
) ENGINE=InnoDB;

CREATE TABLE sales (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    product_id   INT NOT NULL,
    batch_id     INT NULL,
    quantity     INT NOT NULL,
    unit_price   DECIMAL(10,2) NOT NULL,             -- price actually charged
    discount_pct DECIMAL(5,2)  NOT NULL DEFAULT 0,
    sold_on      DATE NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (batch_id)   REFERENCES batches(id) ON DELETE SET NULL,
    INDEX idx_sales_product_date (product_id, sold_on)
) ENGINE=InnoDB;

CREATE TABLE partners (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    name    VARCHAR(120) NOT NULL,
    kind    ENUM('food_bank','charity','shelter','farm','compost') NOT NULL DEFAULT 'charity',
    area    VARCHAR(80),
    phone   VARCHAR(30)
) ENGINE=InnoDB;

CREATE TABLE actions (                               -- AI recommendations
    id           INT AUTO_INCREMENT PRIMARY KEY,
    batch_id     INT NOT NULL,
    action_type  ENUM('discount','donate','markdown') NOT NULL,
    discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
    qty_affected INT NOT NULL DEFAULT 0,
    urgency      ENUM('critical','high','medium') NOT NULL DEFAULT 'medium',
    rationale    VARCHAR(255),
    est_value    DECIMAL(12,2) NOT NULL DEFAULT 0,
    status       ENUM('pending','applied','dismissed') NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at  DATETIME NULL,
    FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE,
    INDEX idx_actions_status (status)
) ENGINE=InnoDB;

CREATE TABLE donations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    product_id  INT NOT NULL,
    batch_id    INT NULL,
    partner_id  INT NOT NULL,
    quantity    INT NOT NULL,
    kg          DECIMAL(8,2) NOT NULL,
    meals       INT NOT NULL,
    donated_on  DATE NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (batch_id)   REFERENCES batches(id) ON DELETE SET NULL,
    FOREIGN KEY (partner_id) REFERENCES partners(id)
) ENGINE=InnoDB;

CREATE TABLE waste_log (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    batch_id   INT NULL,
    quantity   INT NOT NULL,
    kg         DECIMAL(8,2) NOT NULL,
    cost_loss  DECIMAL(12,2) NOT NULL,
    reason     ENUM('expired','damaged','other') NOT NULL DEFAULT 'expired',
    logged_on  DATE NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (batch_id)   REFERENCES batches(id) ON DELETE SET NULL
) ENGINE=InnoDB;
