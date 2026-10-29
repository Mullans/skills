---
name: session-learning
description: Use when explicitly invoked to preserve evidence-backed project or machine-local lessons, reflect on accumulated guidance, inspect learning activity or configuration, or mine Codex history for verified recovery patterns without retaining transcripts.
---

# Session Learning

Preserve the smallest evidence-backed guidance that changes a comparable future task.

Use Python 3.10+: `python <skill-root>/scripts/session_learning.py <command> --root <project>`. Consult command `--help` for arguments.

## Choose the requested mode

- Fresh-session learning: follow the retrospective below.
- Review existing guidance: follow [references/reflection.md](references/reflection.md).
- Inspect or change configuration/activity: read [references/configuration-and-activity.md](references/configuration-and-activity.md).
- Inspect prior sessions: read [references/history-mining.md](references/history-mining.md) before historical mining or recovery-pair authoring. Mine only when requested or explicitly included in the retrospective.

## Retrospective

1. Read [references/decision-policy.md](references/decision-policy.md); its evidence, promotion, reconciliation, privacy, and usage gates are mandatory.
2. Resolve the project root. If `.agents/learning` exists, follow [references/schema-compatibility.md](references/schema-compatibility.md) before proceeding. Otherwise load compatibility guidance only for migration candidates or version errors.
3. Run `retrospective-context --root <root> <terms>` once. Stop authoring if `can_author` is false; inspect `audit --root <root> --authority both --json`. Resolve errors before writing.
4. Compare visible session evidence and applicable instructions/enforcement with compact lesson summaries first. For additional matches, use `search <terms> --summary --json --authority both`; follow `next_page` with the same query/filters and reuse screened results. Inspect only plausible overlaps with `read <id> --authority <matched-authority>`, optionally `--fields <needed-fields>`. Read complete selected fields when `truncated_fields` or omitted details prevent duplicate/conflict reconciliation. Stop searching once reconciliation is supported.
5. Check preflight's `drafts`: if `reviewable`, `interrupted_acceptance`, or `issue_total` is nonzero, follow [references/draft-review.md](references/draft-review.md). Otherwise skip draft lookup.
6. Before choosing/changing authority, equivalence, or delivery, read [references/authority-routing.md](references/authority-routing.md). Existing same-authority confirmation needs no new routing decision.
7. In [references/patch-authoring.md](references/patch-authoring.md), read only the relevant operation section and Finish before canonical mutation. Also read Advanced update contracts for manifests or scope/conflict/usage/equivalence changes. Use `submit-evidence` for confirmation, `update-lesson` for one existing lesson, `create-lesson` for one new lesson, `apply-manifest` for coordinated records, or `accept-draft` for draft acceptance.
8. Run `audit --root <root> --authority both` separately. Distinguish structural failures from stored hook diagnostics. Report the outcome using decision policy; when migration candidates remain, follow compatibility guidance after confirming the primary write.

## Authorization and permissions

Explicit invocation authorizes scoped canonical writes to `<project>/.session-learning` and that project's hashed personal store under `~/.agents/learning/projects/`. It grants no global memory or unrelated implementation authority. Changes to capture criteria, reminders, configuration, or skill implementation require a separate request.

Keep mutable project state in `.session-learning`. Protected instruction/skill projections and personal-store writes may require host permission approval. Prepare the scoped change and retain rollback; report blocked permissions rather than weakening the sandbox or switching authority.

Automatic capture requires individual project consent and remains noncanonical until explicit retrospective acceptance. A failed capture ends that attempt; continue the primary task.
