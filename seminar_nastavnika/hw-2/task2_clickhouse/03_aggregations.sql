USE hw2;

-- 1. Группировка по payment_status
SELECT
    payment_status,
    count()                    AS orders_count,
    round(sum(total_amount),2) AS total_amount,
    round(avg(total_amount),2) AS avg_order
FROM hw2.orders
GROUP BY payment_status
ORDER BY total_amount DESC;

-- 2. JOIN с order_items:
SELECT
    o.payment_status                              AS payment_status,
    sum(oi.quantity)                              AS items_qty,
    round(sum(oi.quantity * oi.product_price), 2) AS items_total,
    round(avg(oi.product_price), 2)               AS avg_product_price
FROM hw2.orders       AS o
INNER JOIN hw2.order_items AS oi USING (order_id)
GROUP BY o.payment_status
ORDER BY items_total DESC;

-- 2a. Та же метрика без привязки к статусу — просто по всему order_items
SELECT
    sum(quantity)                               AS total_items,
    round(sum(quantity * product_price), 2)     AS total_items_amount,
    round(avg(product_price), 2)                AS avg_product_price,
    count(DISTINCT product_name)                AS uniq_products
FROM hw2.order_items;

-- 3. Статистика по датам
SELECT
    toDate(order_date)             AS order_day,
    count()                        AS orders_count,
    round(sum(total_amount), 2)    AS total_amount
FROM hw2.orders
GROUP BY order_day
ORDER BY order_day;

-- 4. Самые активные пользователи
SELECT
    user_id,
    count()                        AS orders_count,
    round(sum(total_amount), 2)    AS total_amount,
    round(avg(total_amount), 2)    AS avg_order
FROM hw2.orders
GROUP BY user_id
ORDER BY total_amount DESC
LIMIT 10;

-- 5. Топ продуктов по выручке
SELECT
    product_name,
    sum(quantity)                               AS qty_sold,
    round(sum(quantity * product_price), 2)     AS revenue
FROM hw2.order_items
GROUP BY product_name
ORDER BY revenue DESC;

-- 6. Доля paid/pending/cancelled в общей выручке (оконные функции)
SELECT
    payment_status,
    round(sum(total_amount), 2)                                AS status_amount,
    round(sum(total_amount) / sum(sum(total_amount)) OVER (), 4) AS share
FROM hw2.orders
GROUP BY payment_status
ORDER BY status_amount DESC;
