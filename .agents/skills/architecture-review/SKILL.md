---
name: architecture-review
description: Statically review architecture changes, module boundaries, aggregates, transaction ownership and integration dependencies against approved requirements and the assigned refactoring stage.
---

# Architecture Review

Review an architecture change as a bounded logical block, using repository
and requirements evidence. Do not implement fixes during this review.

## Workflow

1. Establish the task, agreed comparison base, affected services and stage.
   Read applicable repository/service instructions and relevant Q, AR, BR,
   INV and NFR references. Inspect the diff and relevant surrounding code;
   state assumptions and missing evidence explicitly.
2. Check repository and module structure against the applicable target.
   Trace ownership of models, repositories, routers and business operations.
   Check that shared technical mechanisms remain centralized and that new
   files or abstractions have a justified responsibility.
3. Trace actual business dependencies and cross-module reads and writes.
   Check for ownership bypasses, cyclic business dependencies, internal HTTP
   calls, inappropriate coupling and cross-service database access. Distinguish
   ORM relationships and composition-root imports from business dependencies.
4. For aggregates in the authorized stage, inspect root operations, child
   mutations, repository interfaces, loading strategy and invariant protection.
   Check combined ORM/domain models for implicit I/O and inappropriate
   framework or transport dependencies. Do not require removal of transitional
   item repositories during structural refactoring. Do not require a separate
   domain layer or new business rules not authorized by the task.
5. Trace application-service transaction boundaries, grouped UoW, shared
   AsyncSession, commit/rollback, rollback-only, nesting, resource cleanup and
   concurrent access. Check that external HTTP calls do not extend local
   transactions and that existing catalog-specific guarantees are preserved.
6. Trace DI and lifespan, port ownership, concrete adapter wiring, transport
   error semantics and API/DTO boundaries. Check contract compatibility and
   distinguish business retry policies from transport mechanisms. Apply only
   the requirements relevant to the authorized stage.
7. Compare behavior before and after the change using available code and
   tests. Check for scope creep, security regressions, unintended schema or
   contract changes and lost tests. Flag migration concerns for a separate
   migration-review where applicable. Static review is not runtime verification.
8. Report findings in severity order, with affected component, relevant
   requirement ID, file/line evidence, impact or scenario and a concrete
   recommendation. Classify each as confirmed defect, potential risk,
   architecture trade-off, out-of-scope gap or optional improvement.

## Report

- Scope, comparison base and applicable requirements.
- Findings (highest severity first), with evidence and recommendations.
- Remaining uncertainties and applicable runtime checks.
- If no defect is found, state that explicitly without claiming the system
  is fully verified or the task is Done.

Use read-only repository inspection. Do not modify files, execute application
code or tests, run migrations, connect to a database, or perform Git write
operations. Leave implementation, runtime verification and acceptance to
separately authorized tasks.
