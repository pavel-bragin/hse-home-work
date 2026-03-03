# Data Mart: City Top Products

Проект по сборке витрины данных с использованием PySpark в Yandex Cloud (Apache Zeppelin).

## Описание задачи
Сборка витрины `mart_city_top_products` на основе сырых таблиц `users`, `orders` и `products`.
Витрина рассчитывает количество заказов, проданных единиц и общую выручку по каждому товару в разрезе городов, а затем выделяет Топ-2 самых прибыльных товара для каждого города.

## Стек технологий
Все развернуто в Yandex Cloud, в Yandex Data Processing
* Apache Spark (PySpark)
* Yandex Data Processing (Hadoop, YARN, Zeppelin)
* HDFS / S3 (Yandex Object Storage)

## Структура репозитория
* `notebooks/` — экспортированный Zeppelin-ноутбук с решением и его ipynb версия.