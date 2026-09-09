---
name: session-learning
description: Use when explicitly invoked near the end of a coding session to preserve evidence-backed project or machine-local lessons, reconcile prior guidance, or mine Codex history for verified recovery patterns without retaining transcripts.
---

# Session Learning

Turn observed corrections and outcomes into the smallest durable guidance that improves a comparable future task. Hooks retrieve active lessons; they never inspect transcripts or mutate canonical state.

## Retrospective

1. Read [references/decision-policy.md](references/decision-policy.md). Its evidence, promotion, reconciliation, privacy, conflict, and usage gates are mandatory.
2. Resolve the project root and inspect the visible session or compaction summary, applicable instructions, relevant repository skills/enforcement, and existing lessons in both authorities.
3. Search related lessons with `scripts/session_learning.py search --root <root> --authority both <terms>`.
4. Extract compact evidence before proposing a lesson. Never reconstruct missing history or ask the user to retell the session.
5. Load the specialized reference required by the operation:
   - Read [references/history-mining.md](references/history-mining.md) before historical mining or recovery-pair authoring.
   - Read [references/authority-routing.md](references/authority-routing.md) before choosing/changing authority, equivalence, or delivery.
   - Read [references/patch-authoring.md](references/patch-authoring.md) before any canonical mutation.
6. Gate and reconcile every finding. Ordinary success, generic advice, praise, and transient task state are not lessons.
7. Apply one typed manifest to one authority, then run `validate --root <root> --authority both`. Repair any inconsistency before reporting success.

Invoke the helper as `python <skill-root>/scripts/session_learning.py <command>`. Current commands are `search`, `audit`, `validate`, `mine-history`, `apply-manifest`, `activate`, `rebuild-index`, `set-delivery`, `deactivate`, `reactivate`, `reconcile-delivery`, and `hook`.

## Optional historical mining

Run `mine-history --host codex --root <root>` only when the user asks to inspect prior sessions or when this retrospective explicitly includes history. It is read-only.

- `complete` exits 0 and means the bounded relevant scan completed.
- `failed` exits 1 and provides no trustworthy scan result.
- `degraded` exits 2 and may contain valid completed candidates, but every limitation must be disclosed.

Review compact actionable summaries first and request detail only for candidates being evaluated. Inspect every relevant page or state what remains unreviewed. A filtered or empty page is not proof that no evidence exists.

## Boundaries

- Explicit invocation authorizes scoped writes to `<project>/.agents/learning` and that project's hashed personal store under `~/.agents/learning/projects/`. It authorizes no other home-level memory or unrelated implementation work.
- Preserve compact sanitized evidence, never raw transcripts, logs, prompts, commands, secrets, or normalized event streams.
- Never rewrite a lesson, instruction file, skill, or store wholesale. Existing lessons change only through hash-guarded typed patches and managed projection blocks.
- Never auto-resolve ambiguous conflicts. Keep the new lesson `conflicted`; leave active guidance untouched.
- Prefer existing mechanical enforcement over duplicate prose. Record proposed enforcement without building it during the retrospective.
- Missing runtimes, catalogs, or unsupported hosts fail open to the manual index path.

## Result

For a no-op, say no evidence-backed lesson was found and no files changed. Otherwise report lesson IDs, authority, relation to existing guidance, status/delivery, usage deltas, files changed, and unresolved conflicts or deferrals. Do not retell the session.
