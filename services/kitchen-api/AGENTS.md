# Kitchen API Instructions

The repository-level `AGENTS.md` applies here. This file adds Kitchen API
specifics. Follow the relevant BR, INV, AR and NFR in
`docs/product/REQUIREMENTS.md` (repository-relative path).

## Module boundaries

The target modules under `app/modules/` are:

| Module | Responsibility |
|---|---|
| `catalog` | Local catalog projection; restaurants, branches, menu and availability |
| `catalog/sync` | Atomic snapshot application, revisions, checksum and deduplication |
| `cart` | Cart and its items |
| `orders` | Kitchen order and its items; coordination with Restaurant |
| `checkout` | Coordination of checkout across owning modules |
| `users` | User accounts and customer data |
| `auth` | Authentication, tokens and sessions |

Allowed business dependencies (AR-DEP):

| Module | May depend on |
|---|---|
| `checkout` | `cart`, `orders`, `catalog`, `users` |
| `cart` | `catalog`, `users` |
| `orders` | `catalog`, `users` |
| `auth` | `users` |
| `catalog`, `users` | No other business modules |

These are business dependencies, not a prohibition on technical ORM
relationships, shared infrastructure or composition-root wiring.
Use agreed interfaces; do not bypass the owning module's write operations.
Checkout does not own cart, order or user data. Do not add its own persistence
without a separately approved need.

Keep shared database machinery, base repositories, grouped Unit of Work and
Restaurant HTTP adapters in service infrastructure. Keep configuration,
composition and resource lifecycle in core/application entry points.
The target layout applies according to the assigned refactoring stage;
inspect actual paths before editing rather than assuming migration is complete.

## Invariants and contracts

- Kitchen owns customer accounts, carts and its local order records.
  Restaurant is authoritative for the source catalog, order acceptance and
  business statuses. Do not invent a Restaurant decision.
- Preserve cart ownership, the one-cart-per-customer-and-branch rule and
  separation of items by branch.
- Cart and Order are aggregate roots. Once their domain refactoring is
  complete, mutate children through their roots and public aggregate
  repositories. Do not prematurely remove transitional item repositories.
- Preserve order identity, idempotency, historical order data and the
  distinction between rejection and an unknown or pending result.
- Preserve atomic snapshot application, deduplication, revision ordering and
  stale-update protection, including existing concurrency guarantees.
- Keep transaction boundaries explicit and external HTTP calls outside open
  database transactions. Do not issue application SQL from routers or domain
  models; use repositories and Unit of Work for persistence.
- Compare relevant approved requirements with actual models, migrations,
  services, contracts and tests. Do not implement unrelated gaps merely
  because the target requirements describe them.
- Coordinate changes to SQLAlchemy models, migrations, schemas and HTTP
  contracts. Do not change one representation in isolation.

## Identity and access

- Keep account ownership in `users` and authentication/session management
  in `auth`, according to AR-MOD and BR-IDENTITY.
- Preserve approved password hashing, token security and account verification
  rules. Do not expose passwords, stored credential hashes, private keys or
  tokens in logs or unintended API responses. Deliver tokens only through
  the explicitly approved authentication contract.
- Apply authentication, authorization and resource ownership checks where
  required. Do not trust caller-supplied identity headers as proof of identity.
- Preserve already implemented security protections when moving code.
  Do not implement new authentication features or change token semantics
  unless the assigned task authorizes them.

## Verification

- Run `uv run ruff check .`, applicable formatting checks and
  `uv run pytest ...` from `services/kitchen-api`.
- Tests use database fixtures that can create and drop schema objects.
  Inspect the actual fixture/configuration path (currently `.env.test` and
  `test_database_url`); verify the resolved URL and any overrides point to
  a dedicated disposable test database before running those tests.
  Do not run them when isolation is uncertain.
- When moving ORM models, verify registration, relationships, Alembic
  `target_metadata` and historical migration imports. Review changes for
  unintended schema drift, locking, compatibility and data preservation.
- When touching cart, order or sync flows, verify applicable ownership,
  idempotency, transaction, concurrency and contract scenarios.
- Execute migration verification only against a verified safe disposable target.
