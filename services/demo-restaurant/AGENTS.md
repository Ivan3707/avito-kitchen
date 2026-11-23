# Demo Restaurant Instructions

The repository-level `AGENTS.md` applies here. This file only adds
Demo Restaurant specifics.

## Ownership and boundaries

- Demo Restaurant is the source of truth for its catalog, branch prices
  and availability, order acceptance and order business statuses. It owns
  its PostgreSQL database; Kitchen stores only its synchronized view.
- Keep HTTP handling and validation in `app/api/main.py` and Pydantic
  schemas, business behavior in `app/service`, and persistence in
  `app/infrastructure/repositories` behind `UnitOfWork`.
- Treat each `UnitOfWork` context as a transaction boundary. Repositories
  must not commit, and the database transaction used to build a snapshot
  must close before the HTTP request to Kitchen.

## Integration invariants

- Integrate with Kitchen only through the agreed schemas and client in
  this service. Do not change integration paths, payloads, error meanings
  or schema versions without a separate contract task covering both
  services.
- Preserve order-creation idempotency: the same order identifier and
  payload returns the stored result, while reuse with a different payload
  is a conflict and must not create another order.
- Build a full snapshot from one consistent database state and preserve
  its cross-references, identifiers, versions, activity and availability
  rules. A retry of the same logical delivery must reuse the agreed
  snapshot identity and content.
- Distinguish approved target requirements from the current transitional
  contract. Do not migrate to a target contract or repair other known gaps
  unless the assigned task explicitly authorizes it.

## Verification

- Run `uv run ruff check .` and applicable `uv run pytest ...` commands
  from `services/demo-restaurant`.
- Run migrations or tests that access PostgreSQL only after verifying the
  resolved database URL is a dedicated disposable test environment. Never
  point schema creation, schema removal or migration commands at shared or
  production data.
- Review migration changes for locking, compatibility and data
  preservation before execution.
