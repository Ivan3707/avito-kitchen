# Avito-Kitchen — backlog решений, задач и идей

> Редакция: 2026-11-22. Идеи не являются утверждёнными требованиями. Согласованные бизнес-правила находятся в `docs/product/REQUIREMENTS.md`; здесь остаются следующие действия и технические вопросы.

## 1. Решения из первоначального списка

| ID | Вопрос | Состояние | Где зафиксировано / следующий шаг |
|---|---|---|---|
| Q-001 | Глобальная ревизия или независимые `branch_version` | **Decided** | Единая `catalog_revision` для ресторана; убрать `branch_version` при миграции, BR-SYNC |
| Q-002 | Семантика retry snapshot | **Decided** | Тот же сформированный snapshot отправляется с тем же ID и содержимым; пересборка = новый snapshot, BR-SYNC |
| Q-003 | Прогнать DB-тесты, миграции и сквозной HTTP на изолированной PostgreSQL/Docker | **Ready for planning** | Выполнить до объявления HTTP baseline проверенным; без доступа к реальным БД |
| Q-004 | Статусы после принятия и право их менять | **Decided** | Строгие переходы `accepted → preparing → ready → completed`; терминальные `rejected`/`completed`, `status_version`, история; BR-ORDER-07, 14–16 |
| Q-005 | Роли и идентификация | **Business rule decided** | `customer`, `admin` + сервисные идентичности; email/password, access JWT + refresh; технические детали ниже |
| Q-006 | HTTP vs Kafka | **Decided** | Сначала Kafka-события каталога и статусов, затем команды создания заказов; браузер → Kitchen остаётся REST/HTTP. Topics и контракты — задача этапа Kafka; BR-KAFKA |
| Q-007 | Доставка/оплата или только передача заказа | **Decided** | В первой версии только передача Restaurant, доставка/оплата — будущие сервисы |

## 2. Реализация и верификация согласованных решений

**Открытых принципиальных бизнес-вопросов для первой версии на 2026-11-22 нет.** Ни одна запись с пометкой `Decided` не означает, что код готов или проверен. Технические подробности контрактов, миграций и инвариантов обсуждаем непосредственно перед задачей Codex. Раздел ниже — рабочий перечень задач, а не новые бизнес-решения.

| ID | Тип | Что требуется | Приоритет | Когда |
|---|---|---|---|---|
| Q-008 | Sync — **Decided** | `catalog_state`, один инкремент на транзакцию изменений, `FOR UPDATE`, snapshot из `REPEATABLE READ` | P0 | Реализовать в блоке sync |
| Q-009 | Sync — **Decided** | Не хранить полный payload в Restaurant DB; HTTP retry неизменен; SHA-256 от канонического бизнес-содержимого; сравнение равных ревизий; история `snapshot_id` 30 дней, текущая ревизия+hash бессрочно | P1 | Реализовать, определить канонизацию и проверить очистку; BR-SYNC-11–13 |
| Q-010 | Модель данных — **Decided** | Цена в копейках в `BranchMenuItem`, nullable для недоступных, backfill и повышение `schema_version` | P0 | Реализовать в блоке каталога |
| Q-011 | Cart/checkout — **Decided** | Вариант A: блокировать изменения при `pending`; `SELECT FOR UPDATE`, `cart_version`, защита от дублей; `accepted_unit_price` и подтверждение любого изменения цены (BR-CART-08) | P0 | Реализовать в блоке checkout |
| Q-012 | Identity — **Decided** | Access JWT 15 мин; opaque refresh 14 дней, rotation/revocation, email verification и password reset; `customer`/`admin`, отдельные service identity; защищённый Admin API | P1 | Реализовать блок identity по BR-IDENTITY |
| Q-013 | Status — **Decided** | HTTP Webhook Restaurant → Kitchen через Transactional Outbox, worker с повторами, аутентификация сервиса, `event_id`/`status_version` и идемпотентный приём; адресная сверка при сбоях; без регулярного polling | P1 | Реализовать в блоке жизненного цикла; BR-ORDER-16–19 |
| Q-014 | Kafka — **Decided (architecture)** | Одно delta-событие на транзакцию; строгий `current+1`, пропуски → полный snapshot; producer Outbox, consumer Inbox+`event_id`; retry/backoff и DLQ без пропуска ревизий | P1 | Спроектировать topics, payload, ключи/consumer groups, DLQ recovery и тесты на этапе Kafka; BR-SYNC-14–15, BR-KAFKA |
| Q-015 | Review | Завершить ревью текущего рефакторинга по логическим блокам, сопоставить с новыми правилами | P0 | Текущий этап |
| Q-016 | Documentation | Добавить финальные `docs/ROADMAP.md`, `docs/product/REQUIREMENTS.md`, `docs/product/BACKLOG.md` в Git через согласованную ветку, затем проверить diff/commit | P0 | Первый следующий практический шаг |
| Q-017 | Order recovery — **Decided** | Python-worker + PostgreSQL, исходный `order_id`/payload, 7 автоматических повторов (5с, 15с, 45с, 2м, 5м, 15м, 30м) с jitter; `scheduled`/`leased`/`needs_attention`/`completed`, `FOR UPDATE SKIP LOCKED`, lease, ручное возобновление через Admin API; никогда не выдавать timeout за отказ | P0 | Реализовать и проверить при доработке checkout |

## 3. Плановые последующие этапы и идеи (не входят автоматически в текущую задачу Codex)

Веб-клиент и Kafka входят в согласованный ROADMAP, но ещё не спроектированы до уровня реализации. Прочие IDEA — факультативные учебные расширения. Их наличие здесь **не разрешает Codex реализовывать их без отдельного ТЗ**.

| ID | Идея | Учебная цель | Статус |
|---|---|---|---|
| IDEA-001 | Веб-каталог покупателя и checkout | React/TypeScript, API integration | Planned after backend/Kafka |
| IDEA-002 | Веб-кабинет ресторана | — | Out of scope; вместо него защищённый административный API |
| IDEA-003 | Живые статусы заказа | SSE/WebSocket, eventual consistency | Idea |
| IDEA-004 | Изображения блюд | S3/MinIO, загрузки файлов | Idea |
| IDEA-005 | Redis cache каталога | Инвалидация, TTL, нагрузка | Idea |
| IDEA-006 | Аудит изменений каталога | История версий, диагностика | Idea |
| IDEA-007 | Kafka monitoring и DLQ dashboard | Диагностика доставки, восстановление | Idea |
| IDEA-008 | Распределённая трассировка checkout | OpenTelemetry, correlation ID | Idea |
| IDEA-009 | Нагрузочные сценарии | k6, PostgreSQL EXPLAIN, оптимизация | Idea |
| IDEA-010 | Kubernetes/Helm стенд | Развёртывание, отказоустойчивость | Deferred to DevOps |
| IDEA-011 | Отдельный сервис оплаты | Интеграции, платежные состояния, Saga | Deferred until core ready |
| IDEA-012 | Отдельный сервис доставки | Логистика, статусы доставки | Deferred until core ready |
| IDEA-013 | Рекомендации покупателям | Персонализация, аналитика | Idea |
| IDEA-014 | Акции и промокоды | Правила цен, ограничения применения | Idea |
| IDEA-015 | gRPC эксперимент | Сравнение протоколов межсервисного взаимодействия | Optional experiment |
| IDEA-016 | **Вариант B checkout**: разрешать изменение корзины во время `pending`; после успешного заказа списывать только зафиксированные количества товаров, сохраняя добавленные позже | Конкурентность, версионирование, идемпотентность и корректное списание при асинхронном оформлении | Idea — **отложено**, не реализовывать в первой версии |

## 4. Шаблон новой карточки

```markdown
### Q/IDEA-XXX — Название
- Тип: Feature / Improvement / Bug / Tech debt / Research / Decision
- Статус: Idea / Needs discussion / Ready / In progress / In review / Verification / Done / Deferred
- Какую проблему решает:
- Для кого:
- Варианты решения:
- Влияние на архитектуру и данные:
- Что нужно обсудить:
- DoD / критерии принятия:
- Связанные Issue / PR / ADR / тесты:
```

**Первое практическое действие:** коммит документации без изменений работающего кода; затем безопасный DB/Docker baseline и ревью рефакторинга по логическим блокам. `Q-003`, `Q-015`, `Q-016` не являются закрытыми задачами.

**Приоритеты:** P0 — блокирует согласованный baseline; P1 — нужно к следующему этапу; P2 — полезное улучшение; P3 — эксперимент. Подтверждённые дефекты code review фиксировать с доказательством в реестре PR/Issues и связывать с подходящим Q-ID.
