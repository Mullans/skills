---
name: session-learning
description: Use when explicitly invoked to preserve evidence-backed project or machine-local lessons, reflect on accumulated guidance, inspect learning activity or configuration, or mine Codex history for verified recovery patterns without retaining transcripts.
---

# Session Learning

Turn observed corrections and outcomes into the smallest durable guidance that improves a comparable future task. Hooks retrieve active lessons; they never inspect transcripts or mutate canonical state.

## Choose the requested mode

- For fresh-session learning, use the retrospective below.
- For semantic review of accumulated canonical knowledge, read [references/reflection.md](references/reflection.md) and follow its snapshot and maintenance workflow. Reflection does not codify drafts or mine history.
- For configuration or activity inspection, read [references/configuration-and-activity.md](references/configuration-and-activity.md). These operations work independently of installation location.

Invoke helpers with Python 3.10+: `python <skill-root>/scripts/session_learning.py <command> --root <project>`. Use `python3` or `py -3` where appropriate. Hooks additionally require Node.js 22+ on the host application's PATH.

## Retrospective

For stores created before 0.7.0, move `<project>/.agents/learning` to `<project>/.session-learning` from your normal terminal, preserving its contents. Update the learning-index pointer in your project instructions to `.session-learning/index.md`; if the destination already exists, reconcile the directories before moving.

1. Read [references/decision-policy.md](references/decision-policy.md) and [references/schema-compatibility.md](references/schema-compatibility.md) together when tools support batching. The evidence, promotion, reconciliation, privacy, conflict, usage, and compatibility gates are mandatory.
2. Resolve the project root and run `scripts/session_learning.py retrospective-context --root <root> <terms>` once for the current correction. Its bounded output combines both-store health, migration candidates, and related lessons. Stop authoring when `can_author` is false; inspect the full `audit --root <root> --authority both --json` report to resolve errors. If related lessons or migration candidates are truncated, use focused `search` or `audit` calls before deciding.
3. Inspect the visible session or compaction summary, applicable instructions, and relevant repository skills/enforcement. Run `pending-drafts --page 1`; when drafts or interrupted handoffs exist, read [references/draft-review.md](references/draft-review.md). Review subsequent pages or state the uncovered backlog. Compare related lessons and instructions with the proposed guidance. Extract compact evidence before proposing a lesson; never reconstruct missing history or ask the user to retell the session.
4. Load the specialized reference required by the operation, batching the authoring references after a candidate survives:
   - Read [references/history-mining.md](references/history-mining.md) before historical mining or recovery-pair authoring.
   - Read [references/authority-routing.md](references/authority-routing.md) before choosing/changing authority, equivalence, or delivery.
   - Read [references/patch-authoring.md](references/patch-authoring.md) before any canonical mutation.
5. Gate and reconcile every finding. Ordinary success, generic advice, praise, and transient task state are not lessons.
6. Apply one typed manifest to one authority (`apply-manifest -` reads JSON from standard input), then run `audit --root <root> --authority both`. Keep the post-write audit distinct so an audit error is not mistaken for a rolled-back write. Repair errors before reporting success. Report the requested lesson as saved before mentioning migration candidates. If supported outdated lessons remain, offer to run `scripts/session_learning_migrate.py --root <root> --authority both --host <active-host>` as a separate follow-up; a declined, unanswered, or failed migration leaves the newly written lesson intact.

Use `--help` for command arguments. Invoke the migration helper as `python <skill-root>/scripts/session_learning_migrate.py`.

## Optional historical mining

Run `mine-history --host codex --root <root>` only when the user asks to inspect prior sessions or when this retrospective explicitly includes history. It is read-only.

- `complete` exits 0 and means the bounded relevant scan completed.
- `failed` exits 1 and provides no trustworthy scan result.
- `degraded` exits 2 and may contain valid completed candidates, but every limitation must be disclosed.

Review compact actionable summaries first and request detail only for candidates being evaluated. Inspect every relevant page or state what remains unreviewed. A filtered or empty page is not proof that no evidence exists.

## Boundaries

- Explicit invocation authorizes scoped writes to `<project>/.session-learning` and that project's hashed personal store under `~/.agents/learning/projects/`. It authorizes no other home-level memory or unrelated implementation work.
- Automatic draft capture requires individual project consent. Hooks expose a compact pointer only when enabled; the gated helper supplies capture instructions. Drafts stay machine-local and never become retrievable guidance before explicit retrospective acceptance. Failed capture must not interrupt the primary task.
- Reflection may maintain grounded canonical guidance. Changes to capture criteria, reminders, configuration, or the skill implementation are concrete proposals requiring separate approval.
- Authorization and filesystem permission are separate. Codex protects existing workspace `.agents` and `.codex` directories recursively. Keep mutable project state in `.session-learning`; instruction and skill projections under protected paths and home-store writes need the host's supported permission approval when blocked. Prepare the scoped change first, retain rollback, and report unavailable permissions; never weaken sandbox configuration. Local authority remains personal guidance for this project and retains its separate home location.
- Preserve compact sanitized evidence, never raw transcripts, logs, prompts, commands, secrets, or normalized event streams.
- Never rewrite a lesson, instruction file, skill, or store wholesale. Existing lessons change only through hash-guarded typed patches and managed projection blocks.
- Never auto-resolve ambiguous conflicts. Keep the new lesson `conflicted`; leave active guidance untouched.
- Prefer existing mechanical enforcement over duplicate prose. Record proposed enforcement without building it during the retrospective.
- Automatic retrieval is advisory once the launcher starts: missing Python, invalid state or catalogs, unexpected engine errors, and unsupported hosts return normally. Engine-detected retrieval failures create bounded, deduplicated, privacy-safe reports for `audit`. A missing Node executable or failure before the engine starts cannot be diagnosed by the engine; inspect host launch errors separately. Successful hooks create no error reports.

## Result

For a no-op, say no evidence-backed lesson was found and no files changed. Otherwise report lesson IDs, authority, relation to existing guidance, status/delivery, usage deltas, files changed, and unresolved conflicts or deferrals. After confirming the primary write, disclose migration candidates and offer migration. Do not retell the session.
