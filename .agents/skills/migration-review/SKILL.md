---
name: migration-review
description: Statically review changed or relocated SQLAlchemy models, Alembic migrations and metadata registration for schema consistency, migration safety and data compatibility.
---

# Migration Review

Review schema-related changes and ORM moves without executing migrations.

## Workflow

1. Establish the agreed comparison base and assigned scope. Identify changed
   or moved SQLAlchemy models, Alembic revisions and related schema code.
   Distinguish intended schema changes from structural refactoring.
2. Trace affected tables, columns, indexes, constraints, foreign keys,
   revision dependencies and application consumers.
3. Evaluate existing-data risks: destructive operations, type conversions,
   nullability, Python versus server defaults, uniqueness, referential
   integrity, and whether backfill ordering is safe and complete.
4. Assess likely locks, table rewrites, transaction behavior, deployment
   compatibility and behavior with existing rows.
5. For relocated or reorganized models, inspect the shared Declarative Base,
   metadata registration, startup and Alembic model imports, `target_metadata`,
   relationship resolution and foreign-key references. Check historical
   migrations for imports that may have become invalid. Compare schema
   declarations with the baseline for unintended differences.
6. Compare upgrade operations and resulting models with the approved
   requirements in scope (especially AR-DB and applicable business rules).
   Treat target requirements and current implementation as distinct evidence.
7. Review downgrade behavior when provided, including whether it is
   intentionally lossy or cannot restore prior data.
8. Report findings by severity with file and line evidence, impact and a
   concrete recommendation. Distinguish confirmed defects from potential
   risks that depend on runtime data or deployment conditions. Identify any
   out-of-scope gaps separately.

If no defect is found, say so and list residual risks or checks that could
not be completed statically. Static comparison cannot prove that Alembic
runtime discovery, migration execution or real database schema drift checks
will succeed; list the applicable runtime verification still required.

Do not run migrations, import/execute application code, connect to a
database, or modify project files. Use read-only inspection commands only.
