---
name: migration-review
description: Statically review changed SQLAlchemy models and Alembic migrations when migration safety, schema consistency, or data compatibility needs assessment.
---

# Migration Review

Review migration changes without executing them.

## Workflow

1. Establish the comparison base and identify changed SQLAlchemy models,
   Alembic revisions, and related schema code.
2. Trace affected tables, columns, indexes, constraints, foreign keys,
   revision dependencies, and application consumers.
3. Evaluate existing-data risks: destructive operations, type conversions,
   nullability, Python versus server defaults, uniqueness, referential
   integrity, and whether backfill ordering is safe and complete.
4. Assess likely locks, table rewrites, transaction behavior, deployment
   compatibility, and behavior with existing rows.
5. Compare upgrade operations with the resulting models and the approved
   requirements in scope. Treat target requirements and current
   implementation as distinct evidence.
6. Review downgrade behavior when provided, including whether it is
   intentionally lossy or cannot restore prior data.
7. Report findings by severity with file and line evidence, impact, and a
   concrete recommendation. Label each item as a confirmed defect or a
   potential risk that depends on runtime data or deployment conditions.

If no defect is found, say so and list residual risks or checks that could
not be completed statically.

Do not run migrations, connect to a database, or modify project files.
