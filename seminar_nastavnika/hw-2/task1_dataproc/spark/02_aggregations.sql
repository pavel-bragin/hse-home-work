USE hw2;

-- 1. Хорошие валюты
SELECT
    currency,
    COUNT(*)              AS tx_count,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS avg_amount
FROM transactions_v2
WHERE currency IN ('USD', 'EUR', 'RUB') AND amount > 0
GROUP BY currency
ORDER BY total_amount DESC;

-- 2. Fraud vs legit
SELECT
    is_fraud,
    COUNT(*)              AS tx_count,
    ROUND(SUM(amount), 2) AS total_amount,
    ROUND(AVG(amount), 2) AS avg_amount
FROM transactions_v2
WHERE amount > 0
GROUP BY is_fraud;

-- 3. Ежедневная динамика
SELECT
    CAST(transaction_date AS DATE) AS tx_day,
    COUNT(*)                       AS tx_count,
    ROUND(SUM(amount), 2)          AS total_amount,
    ROUND(AVG(amount), 2)          AS avg_amount
FROM transactions_v2
WHERE amount > 0
GROUP BY CAST(transaction_date AS DATE)
ORDER BY tx_day;

-- 4. Разбивка по дню недели / часу
SELECT
    DATE_FORMAT(transaction_date, 'EEEE') AS day_of_week,
    HOUR(transaction_date)                AS hour_of_day,
    COUNT(*)                              AS tx_count,
    ROUND(SUM(amount), 2)                 AS total_amount
FROM transactions_v2
WHERE amount > 0
GROUP BY DATE_FORMAT(transaction_date, 'EEEE'), HOUR(transaction_date)
ORDER BY day_of_week, hour_of_day;

-- 5. Количество логов на транзакцию
SELECT
    t.transaction_id,
    t.user_id,
    t.amount,
    t.currency,
    COUNT(l.log_id) AS log_count
FROM transactions_v2 t
LEFT JOIN logs_v2 l ON t.transaction_id = l.transaction_id
GROUP BY t.transaction_id, t.user_id, t.amount, t.currency
ORDER BY log_count DESC, t.transaction_id;

-- 6. Топ категорий логов (только для валидных транзакций)
SELECT
    l.category,
    COUNT(*)                         AS log_count,
    COUNT(DISTINCT l.transaction_id) AS uniq_tx
FROM logs_v2 l
JOIN transactions_v2 t ON l.transaction_id = t.transaction_id
WHERE t.amount > 0
GROUP BY l.category
ORDER BY log_count DESC;

-- 7. Топ пользователей по обороту в «хороших» валютах
SELECT
    user_id,
    COUNT(*)              AS tx_count,
    ROUND(SUM(amount), 2) AS total_amount
FROM transactions_v2
WHERE currency IN ('USD', 'EUR', 'RUB') AND amount > 0
GROUP BY user_id
ORDER BY total_amount DESC
LIMIT 10;
