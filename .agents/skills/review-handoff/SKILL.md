---
name: review-handoff
description: Prepare a completed implementation for code review when a compact, evidence-based GitHub handoff is needed, including requirement traceability, verification and Git state.
---

# Review Handoff

Produce a reviewer-oriented summary from repository evidence. This skill
collects implementation and verification evidence; it does not replace
code review or perform implementation.

## Workflow

1. Identify the working branch and agreed comparison base. State any
   assumption if the base cannot be confirmed.
2. Collect the commit range, diff, changed-file list, and staged, unstaged
   and untracked changes. Keep unrelated user changes separate. Distinguish
   committed changes available on GitHub from local-only changes; do not
   assert a push or remote SHA without evidence.
3. Map implementation to the assigned task, relevant Q IDs and applicable
   BR, INV, AR and NFR requirements. Identify what is supported by the diff
   and what remains unverified. Flag scope deviations and do not treat future
   approved requirements as current acceptance criteria.
4. Summarize the implementation by logical component and explain important
   behavior, architecture decisions, module ownership or transaction
   boundaries rather than listing every edit.
5. Record only tests and checks supported by command output, CI results or
   another explicit artifact. Include passed, failed and not executed
   checks, reasons when known, and the revision/environment when available.
   Do not infer success from test files or code, or attribute old results to
   newer changes without evidence.
6. List unverified scenarios, migration or deployment concerns, known
   limitations and residual risks. Categorize known findings as confirmed
   defect, potential risk, architecture trade-off, out-of-scope gap or
   optional improvement. A trade-off or gap is not automatically a defect.
7. Record the branch, full commit SHA, comparison base, confirmed remote
   status when available, and whether the working tree contains uncommitted
   changes.
8. Produce a compact GitHub-ready handoff with sections for scope and
   requirements, implementation, verification, risks and Git state. Include
   precise file references where they help the reviewer.

Do not commit, push, merge, alter project files, or run new application tests
while preparing the handoff. Report missing evidence rather than inventing it.
