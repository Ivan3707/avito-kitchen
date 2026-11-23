---
name: review-handoff
description: Prepare a completed implementation for code review when a compact, evidence-based GitHub handoff is needed.
---

# Review Handoff

Produce a reviewer-oriented summary from repository evidence.

## Workflow

1. Identify the working branch and agreed comparison base. State any
   assumption if the base cannot be confirmed.
2. Collect the commit range, diff, changed-file list, and staged, unstaged,
   and untracked changes. Keep unrelated user changes separate.
3. Map the implementation to the assigned task and only the approved
   requirements relevant to it. Flag scope deviations.
4. Summarize the implementation by logical component and explain important
   behavior or transaction boundaries rather than listing every edit.
5. Record only tests and checks supported by command output, CI results, or
   another explicit artifact. Never infer success from test files or code.
6. List unverified scenarios, migration or deployment concerns, known
   limitations, and residual risks.
7. Record the branch, full commit SHA, comparison base, and whether the
   working tree contains uncommitted changes.
8. Produce a compact GitHub-ready handoff with sections for scope,
   implementation, verification, risks, and Git state. Include precise file
   references where they help the reviewer.

Do not commit, push, merge, or alter project files while preparing the
handoff.
