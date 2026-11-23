# Kitchen API Instructions

The repository-level `AGENTS.md` applies here. This file only adds
Kitchen API specifics.

## Boundaries

- Keep routing, dependency wiring, HTTP concerns and request/response
  validation in `app/api` and the Pydantic contract schemas.
- Keep cart, catalog, order and synchronization decisions in
  `app/services`. API handlers must not contain business decisions.
- Access PostgreSQL through `app/infrastructure/repositories` and
  `UnitOfWork`; do not issue application queries from API or service code.
- Treat each `UnitOfWork` context as a transaction boundary. Repositories
  must not commit, and remote calls must not accidentally extend an open
  database transaction.

## Invariants and contracts

- Preserve cart ownership and the one-cart-per-customer-and-branch rule;
  never mix branches in one cart.
- Preserve order identity, historical order data and the distinction
  between rejection and an unknown or pending result.
- Apply catalog snapshots atomically and preserve deduplication, ordering
  and stale-update protections defined for the assigned task.
- When touching these flows, compare the approved requirements with the
  current models, migrations, services and tests. Do not implement an
  unrelated gap merely because the target requirements describe it.
- Coordinate changes to SQLAlchemy models, Alembic migrations, Pydantic
  schemas and HTTP contracts. Do not change one representation in
  isolation.

## Verification

- Run `uv run ruff check .` and applicable `uv run pytest ...` commands
  from `services/kitchen-api`.
- Tests load `test_database_url` from `.env.test` and create and drop the
  schema. Before running any pytest command that uses these fixtures,
  verify that the resolved URL points to a dedicated disposable test
  database. Do not run it when isolation is uncertain.
- Review every migration for locking, compatibility and data preservation;
  execute migrations only against a verified safe target.
