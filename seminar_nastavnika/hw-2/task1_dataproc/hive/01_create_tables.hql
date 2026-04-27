CREATE DATABASE IF NOT EXISTS hw2;
USE hw2;

DROP TABLE IF EXISTS transactions_v2;
CREATE EXTERNAL TABLE transactions_v2 (
    transaction_id   BIGINT,
    user_id          BIGINT,
    amount           DOUBLE,
    currency         STRING,
    transaction_date TIMESTAMP,
    is_fraud         INT
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION 's3a://hse-1/raw/transactions/'
TBLPROPERTIES ('skip.header.line.count'='1');

DROP TABLE IF EXISTS logs_v2;
CREATE EXTERNAL TABLE logs_v2 (
    log_id         BIGINT,
    transaction_id BIGINT,
    category       STRING,
    comment        STRING,
    log_timestamp  TIMESTAMP
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ';'
STORED AS TEXTFILE
LOCATION 's3a://hse-1/raw/logs/'
TBLPROPERTIES ('skip.header.line.count'='1');

-- Быстрая проверка
SELECT COUNT(*) AS tx_cnt  FROM transactions_v2;
SELECT COUNT(*) AS log_cnt FROM logs_v2;
