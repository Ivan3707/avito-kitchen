# Avito.Kitchen

MVP-сервис для интеграции заведений с клиентским приложением.

Проект реализован в рамках тестового задания на Backend Intern и демонстрирует подход к проектированию backend-системы, API-контрактов, схемы данных и интеграции между независимыми сервисами.

Avito.Kitchen предоставляет единый API для клиентской части и интеграции заведений.

Основные возможности:

* просмотр ресторанов и их филиалов;
* получение меню конкретного филиала;
* работа с корзиной;
* оформление заказа;
* проверка актуальности заказа;
* синхронизация каталога и доступности товаров;
* интеграция с внешней системой ресторана.

В репозитории также находится `Demo Restaurant` — отдельный сервис, имитирующий внешнюю систему заведения.

---

# Архитектура

Проект состоит из двух независимых сервисов:

```text
avito-kitchen/
├── services/
│   ├── kitchen-api/
│   │   └── ...
│   │
│   └── demo-restaurant/
│       └── ...
│
├── docs/
│   ├── architecture/
│   │   └── architecture-c4.puml
│   │
│   ├── cjm/
│   │   ├── user-cjm.puml
│   │   └── restaurant-cjm.puml
│   │
│   └── database/
│       └── er-diagram.puml
│
├── openapi/
│   └── openapi.yaml
│
├── docker-compose.yml
└── README.md
```

## Kitchen API

Основной сервис системы.

Отвечает за:

* клиентский HTTP API;
* хранение ресторанного каталога;
* филиалы и меню;
* корзины пользователей;
* создание заказов;
* синхронизацию данных от ресторанов;
* интеграцию с API ресторана.

## Demo Restaurant

Отдельный сервис, имитирующий внешнюю систему ресторана.

Используется для демонстрации интеграции между двумя независимыми backend-сервисами.

Demo Restaurant:

* хранит собственное состояние ресторана;
* формирует snapshot каталога;
* синхронизирует каталог с Kitchen API;
* валидирует заказы;
* принимает созданные заказы.

---

# Документация

В проекте подготовлена документация для основных частей системы.

```text
docs/
├── architecture/
│   └── architecture-c4.puml
│
├── cjm/
│   ├── user-cjm.puml
│   └── restaurant-cjm.puml
│
└── database/
    └── er-diagram.puml
```

## C4 Architecture

Файл:

```text
docs/architecture/architecture-c4.puml
```

Диаграмма описывает взаимодействие основных компонентов системы:

```text
Customer
   │
   ▼
Client Application
   │
   ▼
Kitchen API
   │
   ├──────────────► PostgreSQL
   │
   └──────────────► Demo Restaurant
                         │
                         └──────► Kitchen API
```

---

# Customer Journey

Пользовательский сценарий находится в:

```text
docs/cjm/user-cjm.puml
```

Основной поток:

1. Пользователь получает список ресторанов.
2. Выбирает ресторан и филиал.
3. Получает меню выбранного филиала.
4. Добавляет товары в корзину.
5. Изменяет количество товаров или удаляет их.
6. Оформляет заказ.
7. Kitchen API проверяет актуальность заказа.
8. Заказ передаётся в Demo Restaurant.
9. Пользователь получает результат оформления заказа.

---

# Restaurant Journey

Сценарий взаимодействия со стороны заведения:

```text
docs/cjm/restaurant-cjm.puml
```

Основной поток:

1. Ресторан формирует актуальный snapshot каталога.
2. Snapshot отправляется в Kitchen API.
3. Kitchen API дедуплицирует snapshot по `snapshot_id` и проверяет `generated_at`.
4. Версии каждого филиала проверяются независимо по `branch_version`.
5. Новый согласованный snapshot применяется атомарно, повторный или устаревший — игнорируется.
6. При оформлении заказа Kitchen API взаимодействует с API ресторана.
7. Ресторан валидирует и принимает заказ.

---

# API

Полная OpenAPI-спецификация находится в:

```text
openapi/openapi.yaml
```

## Client API

### Получение ресторанов

```http
GET /api/v1/restaurants
```

Возвращает список ресторанов.

---

### Получение филиалов ресторана

```http
GET /api/v1/restaurants/{restaurant_id}/branches
```

---

### Получение меню филиала

```http
GET /api/v1/branches/{branch_id}/menu
```

Возвращает меню с учётом доступности товаров в конкретном филиале.

---

### Получение корзины

```http
GET /api/v1/branches/{branch_id}/cart
X-User-Email: customer@example.com
```

В MVP пользователь идентифицируется через `X-User-Email`.

Полноценная аутентификация и авторизация не реализуются, поскольку это допускается условиями тестового задания.

---

### Добавление товара в корзину

```http
POST /api/v1/branches/{branch_id}/cart/items
X-User-Email: customer@example.com
```

Пример:

```json
{
  "menu_item_id": "00000000-0000-0000-0000-000000000000",
  "quantity": 2
}
```

---

### Изменение количества товара

```http
PATCH /api/v1/branches/{branch_id}/cart/items/{menu_item_id}
X-User-Email: customer@example.com
```

```json
{
  "quantity": 3
}
```

---

### Удаление товара из корзины

```http
DELETE /api/v1/branches/{branch_id}/cart/items/{menu_item_id}
X-User-Email: customer@example.com
```

---

### Оформление заказа

```http
POST /api/v1/branches/{branch_id}/cart/checkout
X-User-Email: customer@example.com
```

```json
{
  "order_id": "external-order-123"
}
```

`order_id` используется для идентификации логической операции оформления заказа.

---

# Restaurant Integration API

## Синхронизация каталога

```http
POST /integration/v1/sync
```

Ресторан передаёт полный snapshot своего состояния:

* данные ресторана;
* филиалы;
* меню;
* товары;
* доступность товаров по филиалам;
* `snapshot_id`, `schema_version` и время формирования `generated_at`;
* независимую `branch_version` для каждого филиала.

`snapshot_id` обеспечивает идемпотентность доставки, `schema_version` описывает
формат контракта, а `branch_version` защищает конкретный филиал от регрессии.
Kitchen API сериализует конкурентную синхронизацию одного ресторана, атомарно
применяет полный snapshot и игнорирует повторные либо устаревшие данные.

---

## Проверка заказа

```http
POST /integration/v1/orders/validate
```

Проверяются:

* существование филиала;
* возможность филиала принимать заказы;
* существование товара;
* активность товара;
* доступность товара в филиале;
* актуальность цены.

Операция не создаёт заказ и не изменяет состояние ресторана.

---

## Создание заказа

```http
POST /integration/v1/orders
```

Создание заказа идемпотентно.

Внешний `order_id` идентифицирует одну логическую операцию создания заказа.

При повторной отправке:

```text
same order_id
+
same payload
```

возвращается ранее сохранённый результат.

Если `order_id` уже использован с другим payload, запрос отклоняется.

---

# Database

Основное хранилище — PostgreSQL.

ER-диаграмма:

```text
docs/database/er-diagram.puml
```

Основные сущности:

```text
Restaurant
├── RestaurantBranch
├── Menu
│    └── MenuItem
│         └── BranchMenuItem
│
Customer
├── Cart
│    └── CartItem
│
└── Order
     └── OrderItem
```

## Restaurant

Хранит данные ресторана, полученные из внешней системы.

Основные данные:

* внутренний UUID;
* внешний идентификатор;
* название;
* описание;
* идентификатор и время последнего принятого snapshot.

## RestaurantBranch

Филиал ресторана.

Содержит информацию об активности филиала и возможности принимать заказы.

## Menu и MenuItem

Представляют структуру каталога ресторана.

Товар имеет собственный внешний идентификатор, название, описание и статус активности.

## BranchMenuItem

Связывает товар меню с конкретным филиалом.

Это позволяет хранить цену и доступность одного и того же товара отдельно для каждого филиала. Цена хранится в целых копейках и может быть `NULL` только для недоступной позиции.

## Cart

Корзина принадлежит пользователю и конкретному филиалу.

Для пары:

```text
customer + branch
```

существует не более одной активной корзины.

## Order

Локальная запись оформленного заказа.

Заказ содержит:

* пользователя;
* филиал;
* внешний идентификатор операции;
* идентификатор заказа ресторана;
* статус;
* данные товаров заказа.

## OrderItem

Хранит данные товара на момент оформления заказа.

Это позволяет сохранить состояние заказа независимо от последующих изменений каталога.

---

# Data Consistency

## Versioned synchronization

Глобальная версия snapshot не используется. Доставка дедуплицируется по
`snapshot_id`, порядок полных снимков контролируется по `generated_at`, а
регрессия состояния филиала — по его `branch_version`. `schema_version`
зарезервирован только для эволюции wire-контракта.

---

## Idempotent order creation

Для защиты от повторного создания заказа используется внешний `order_id`.

Для повторной обработки одного заказа сохраняется результат операции и используется проверка соответствия исходного payload.

---

## Order snapshots

Заказ хранит данные товаров на момент оформления.

Изменение текущего каталога не изменяет историю уже созданных заказов.

---

# Project Structure

Kitchen API разделён на слои:

```text
app/
├── api/
│   ├── catalog.py
│   ├── cart.py
│   └── integration.py
│
├── core/
│   └── config.py
│
├── infrastructure/
│   ├── clients/
│   ├── database/
│   ├── repositories/
│   └── unit_of_work.py
│
├── integration/
│   └── schemas/
│
└── services/
    ├── catalog.py
    ├── cart.py
    ├── order.py
    └── sync.py
```

## API Layer

Отвечает за HTTP-взаимодействие:

* маршрутизацию;
* параметры запросов;
* headers;
* request/response schemas.

## Service Layer

Содержит прикладную и бизнес-логику:

* синхронизацию каталога;
* работу с корзиной;
* валидацию заказа;
* создание заказа.

## Repository Layer

Инкапсулирует работу с PostgreSQL через SQLAlchemy.

## Unit of Work

Управляет транзакционными границами операции:

```text
begin
  │
  ├── repository operations
  │
  ├── commit
  │
  └── rollback on exception
```

---

# Technology Stack

## Kitchen API

* Python
* FastAPI
* Pydantic
* SQLAlchemy Async
* PostgreSQL
* asyncpg
* Alembic
* httpx
* pytest
* uv

## Infrastructure

* Docker
* Docker Compose

## Code quality

В проекте настроены инструменты проверки качества и форматирования кода:

* Ruff
* pytest

---

# Virtual Environments and Dependencies

Сервисы являются отдельными приложениями и могут иметь собственные зависимости и виртуальные окружения.

Для Kitchen API.

Команды рекомендуется запускать в services/kitchen-api:

```bash
cd services/kitchen-api
uv run <command>
```

```bash
uv run pytest -q
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check .
```
Это гарантирует, что команда будет выполнена с зависимостями, указанными для соответствующего сервиса.

Для Demo Restaurant команды должны выполняться в services/demo-restaurant:
```bash
cd services/demo-restaurant
```
```bash
uv run pytest -q
```
```bash
uv run ruff check .
```
```bash
uv run ruff format --check .
```
---

# Running the Project

Для запуска необходимы:

* Docker;
* Docker Compose.

Запуск:

```bash
docker compose up --build
```

После запуска Kitchen API доступен по адресу:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

OpenAPI JSON, автоматически генерируемый FastAPI:

```text
http://localhost:8000/openapi.json
```

Остановка контейнеров:

```bash
docker compose down
```

Удаление контейнеров вместе с volumes:

```bash
docker compose down -v
```

---

# Database Migrations

Alembic migrations находятся в:

```text
services/kitchen-api/alembic/
```

Для ручного применения миграций внутри контейнера:

```bash
docker compose exec kitchen-api alembic upgrade head
```

---

# Tests

Тесты Kitchen API находятся в:

```text
services/kitchen-api/tests/
```

При локальной разработке из директории `services/kitchen-api`:

```bash
uv run pytest -q
```

При необходимости запуска тестов внутри контейнера:

```bash
docker compose exec kitchen-api pytest -q
```

---

# Static Analysis

Из директории соответствующего Python-сервиса:

```bash
uv run ruff check .
```

Проверка форматирования:

```bash
uv run ruff format --check .
```

Автоматическое форматирование:

```bash
uv run ruff format .
```

---

# Design Decisions

## Full Snapshot Synchronization

Restaurant Integration API принимает полный snapshot состояния каталога.

Такой подход упрощает синхронизацию и восстановление актуального состояния.

Сущности, отсутствующие в новом snapshot, могут быть обработаны как удалённые или переведены в неактивное состояние в соответствии с логикой синхронизации.

---

## Snapshot and Branch Versioning

Каждый snapshot имеет уникальный `snapshot_id`, временную метку `generated_at`
и версию формата `schema_version`. Каждый филиал несёт собственную
`branch_version`. Такое разделение не смешивает идемпотентность доставки,
эволюцию схемы и порядок изменения бизнес-сущностей.

---

## Idempotent Order Creation

HTTP-запросы могут повторяться из-за сетевых ошибок или retry-механизмов.

Поэтому создание заказа построено как идемпотентная операция по внешнему `order_id`.

Повторная доставка одного и того же запроса не должна создавать второй заказ.

---

## Separate Demo Restaurant

Demo Restaurant реализован как отдельный сервис.

Это позволяет продемонстрировать:

* взаимодействие независимых backend-систем;
* разделение ответственности;
* интеграцию через HTTP API;
* независимость моделей данных основного сервиса и внешнего ресторана.

---

# Scope and MVP Limitations

Проект является MVP.

Некоторые production-oriented возможности сознательно не реализованы:

* полноценная аутентификация и авторизация;
* управление пользователями;
* сложная обработка распределённых транзакций;
* брокеры сообщений;
* сложные retry-механизмы;
* production monitoring и observability.

Эти ограничения соответствуют цели тестового задания: показать подход к проектированию backend-системы и реализации основных бизнес-сценариев.

Основные сценарии MVP:

* получение каталога;
* работа с корзиной;
* оформление заказа;
* синхронизация данных ресторана;
* проверка заказа;
* идемпотентное создание заказа;
* интеграция с отдельным сервисом ресторана.

Все сервисы запускаются в одном репозитории через Docker Compose.
