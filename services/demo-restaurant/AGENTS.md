# Demo Restaurant Instructions

The repository-level `AGENTS.md` applies here. This file adds Demo Restaurant
specifics. Follow the relevant BR, INV, AR and NFR in
`docs/product/REQUIREMENTS.md` (repository-relative path).

## Ownership and module boundaries

Demo Restaurant owns its PostgreSQL database and is the source of truth
for its catalog, branch prices and availability, order acceptance and order
business statuses. Kitchen stores its synchronized view.

The target modules under `app/modules/` are:

| Module | Responsibility |
|---|---|
| `catalog` | Source catalog, mutations, revision and catalog state |
| `catalog/sync` | Consistent snapshot construction and delivery to Kitchen |
| `orders` | RestaurantOrder aggregate, order acceptance and business statuses |

Orders may depend on Catalog through agreed interfaces. Catalog must not
have a reverse business dependency on Orders. Technical ORM relationships
and composition-root wiring are distinct from business dependencies.

Keep shared database machinery, base repositories, grouped Unit of Work and
Kitchen HTTP adapters in service infrastructure. Keep common security
mechanisms in `core/security/` when needed. Admin routes belong to the owning
business modules, not a separate admin module; they must invoke business
operations rather than bypassing them through direct SQL or repository writes.

The target layout applies according to the assigned refactoring stage;
inspect actual paths before editing rather than assuming migration is complete.

## Catalog consistency

- Preserve the catalog revision protocol in BR-SYNC, including the
  catalog-state row lock and approved write transaction boundary.
- Increment `catalog_revision` exactly once per transaction with a changed
  final catalog state; do not increment for rollback or effective no-op.
- Preserve `CatalogMutationService` semantics, rollback-only behavior and
  the prohibition on intermediate manual commit/rollback for catalog
  mutations. Caught exceptions must not allow partial catalog changes to
  be committed.
- Build full snapshots from one consistent database state with the approved
  REPEATABLE READ isolation level. Close the reading transaction before
  sending the HTTP request to Kitchen.
- Preserve snapshot cross-references, identifiers, versions, checksum,
  activity and availability rules. Retry of the same logical delivery must
  reuse the agreed snapshot identity and content.

## Orders and integration invariants

- RestaurantOrder is the aggregate root. Once domain refactoring is complete,
  mutate child items through the root and public aggregate repository; do
  not prematurely remove transitional item repositories.
- Preserve order-creation idempotency: the same identifier and payload
  return the stored result; reuse with different content conflicts and must
  not create another order. Preserve historical order data.
- Keep all approved catalog and order concurrency guarantees. Access
  catalog data via agreed interfaces rather than modifying it from Orders.
- Integrate with Kitchen through approved contracts and service-local
  adapters. Do not change paths, payloads, error meanings or schema versions
  without an explicitly approved coordinated contract task.
- Preserve separate user/admin and service identity requirements within
  the authorized scope; never bypass authorization for convenience.
- Distinguish approved target requirements from current transitional
  behavior. Do not implement future status transitions, delivery mechanisms
  or unrelated gaps unless explicitly assigned.

## Verification

- Run `uv run ruff check .`, applicable formatting checks and
  `uv run pytest ...` from `services/demo-restaurant`.
- Run tests or migrations that access PostgreSQL only after verifying the
  resolved database configuration, overrides and isolation. Use a dedicated
  disposable verification target. Never point schema creation, removal or
  migration verification at shared or production data.
- When moving ORM models, verify registration, relationships, Alembic
  `target_metadata` and historical migration imports. Review changes for
  unintended schema drift, locking, compatibility and data preservation.
- When touching catalog or sync, verify applicable revision, no-op, rollback,
  concurrent mutation and snapshot consistency scenarios. When touching
  orders, verify applicable idempotency and contract scenarios.
