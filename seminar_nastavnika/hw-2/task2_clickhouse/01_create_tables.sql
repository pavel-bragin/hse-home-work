CREATE DATABASE IF NOT EXISTS hw2;

DROP TABLE IF EXISTS hw2.orders;
CREATE TABLE hw2.orders
(
    order_id       UInt64,
    user_id        UInt64,
    order_date     DateTime,
    total_amount   Float64,
    payment_status LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY (order_date, order_id);

DROP TABLE IF EXISTS hw2.order_items;
CREATE TABLE hw2.order_items
(
    item_id       UInt64,
    order_id      UInt64,
    product_name  String,
    product_price Float64,
    quantity      UInt32
)
ENGINE = MergeTree
ORDER BY (order_id, item_id);
