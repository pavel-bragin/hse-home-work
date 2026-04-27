
INSERT INTO hw2.orders
SELECT
    order_id,
    user_id,
    parseDateTimeBestEffort(order_date) AS order_date,
    total_amount,
    payment_status
FROM s3(
    'https://storage.yandexcloud.net/hse-1/raw/orders.csv',
    'YCAJEDTMTyNtmX4cIweFNyasT',
    'YCNk-ooZMv5K3wwAMGBrGAZtvKinzFL1Z4yyw6UK',
    'CSVWithNames',
    'order_id UInt64, user_id UInt64, order_date String, total_amount Float64, payment_status String'
);

INSERT INTO hw2.order_items
SELECT
    item_id,
    order_id,
    product_name,
    product_price,
    quantity
FROM s3(
    'https://storage.yandexcloud.net/hse-1/raw/order_items.txt',
    'YCAJEDTMTyNtmX4cIweFNyasT',
    'YCNk-ooZMv5K3wwAMGBrGAZtvKinzFL1Z4yyw6UK',
    'CSVWithNames',
    'item_id UInt64, order_id UInt64, product_name String, product_price Float64, quantity UInt32'
)
SETTINGS format_csv_delimiter = ';';

SELECT count() AS orders_cnt      FROM hw2.orders;
SELECT count() AS order_items_cnt FROM hw2.order_items;