# Павел Брагин, NoSQL HW: 

Проект демонстрирует БД студентов университета на `MongoDB` с горизонтальным масштабированием через шардинг. В репозитории есть:

- шардированный кластер `MongoDB` на `Docker Compose`;
- консольный интерфейс на `Python`;
- генератор тестовых данных;
- нагрузочное тестирование с сохранением `CSV` и графиков;
- отчёт для сдачи.

## Архитектура

Используется кластер из пяти сервисов:

- `cfgsvr1` - config server replica set;
- `shard1a` - первый shard replica set;
- `shard2a` - второй shard replica set;
- `mongos` - роутер для клиентских запросов;

Коллекция `university.students` шардируется по ключу `{ _id: "hashed" }`.

## Структура проекта

```text
.
├── docker-compose.yml
├── requirements.txt
├── scripts
│   ├── benchmark.py
│   ├── seed_data.py
│   └── show_shard_distribution.js
├── src
│   ├── config.py
│   ├── db.py
│   ├── repository.py
│   └── university_cli.py
└── report
    └── report.md
```

## Быстрый старт

### 1. Поднять кластер

```bash
docker compose up -d
```

Проверить, что инициализация завершилась:

```bash
docker compose logs replset-init
docker compose logs sharding-init
```

### 2. Установить зависимости Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Загрузить тестовые данные

```bash
python3 scripts/seed_data.py --count 10000
```

### 4. Использовать CLI

Добавить студента:

```bash
python3 -m src.university_cli add-student \
  --student-id S900001 \
  --full-name "Pavel Bragin" \
  --faculty "Computer Science" \
  --program "Data Engineering" \
  --year 2 \
  --group-number "CS-21" \
  --email "pavel.bragin@edu.hse.ru"
```

Посмотреть студента:

```bash
python3 -m src.university_cli get-student --student-id S900001
```

Обновить GPA:

```bash
python3 -m src.university_cli update-gpa --student-id S900001 --gpa 4.8
```

Добавить запись о курсе:

```bash
python3 -m src.university_cli add-enrollment \
  --student-id S900001 \
  --course-code DE301 \
  --title "Distributed Data Systems" \
  --semester "2026-spring" \
  --credits 5 \
  --grade A
```

Получить агрегированную статистику:

```bash
python3 -m src.university_cli faculty-stats
```

### 5. Проверить распределение по шардам

```bash
docker compose exec mongos mongosh --file /scripts/show_shard_distribution.js
```

Если файл недоступен внутри контейнера, можно выполнить напрямую:

```bash
docker compose exec mongos mongosh --eval 'db = db.getSiblingDB("university"); db.students.getShardDistribution();'
```

## Нагрузочное тестирование

```bash
python3 scripts/benchmark.py \
  --operations-per-run 20000 \
  --warmup-operations 3000 \
  --concurrency-levels 4,8,16,32,64 \
  --repeats 3
```

Скрипт создаёт:

- `benchmark_results/benchmark_summary.csv`
- `benchmark_results/benchmark_runs.csv`
- `benchmark_results/benchmark_operation_breakdown.csv`
- `benchmark_results/benchmark_operation_summary.csv`
- `benchmark_results/throughput_vs_concurrency.png`
- `benchmark_results/latency_vs_concurrency.png`
- `benchmark_results/throughput_latency_tradeoff.png`
- `benchmark_results/operation_latency_heatmap.png`
- `benchmark_results/benchmark_dashboard.png`

## Схема документа

Пример документа в коллекции `students`:

```json
{
  "_id": "S000001",
  "student_id": "S000001",
  "full_name": "Anna Petrova",
  "faculty": "Computer Science",
  "program": "Data Engineering",
  "year": 2,
  "group_number": "CS-24",
  "contacts": {
    "email": "s000001@university.local"
  },
  "gpa": 4.6,
  "status": "active",
  "enrollments": [
    {
      "course_code": "DB101",
      "title": "Databases",
      "semester": "2025-autumn",
      "credits": 4,
      "grade": "A"
    }
  ],
  "created_at": "2026-03-18T00:00:00Z",
  "updated_at": "2026-03-18T00:00:00Z"
}
```

## Отчёт

Готовый шаблон и описание решения находятся в `report/report.md`.
