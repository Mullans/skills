# Session Learning Decision Policy

Read this policy for every explicit retrospective. Corrections and observed outcomes are evidence; analyzer interpretations are hypotheses; lessons are gated conclusions.

## Epistemic hierarchy

Prefer evidence in this order:

1. explicit user correction or durable convention;
2. decisive test, runtime, CI, review, or repository result;
3. a successfully verified non-obvious correction or workflow;
4. repeated independent observations;
5. analyzer inference.

Never promote an inference merely because it is plausible, frequent, recent, or adjacent to success. Current-session and historical recovery pairs use the same causal and contrast gates.

## Diagnosis and remedy

Before proposing a lesson, classify observed friction using only categories supported by the reviewed evidence:

| Observed problem | Inspect | Preferred remedy |
| --- | --- | --- |
| Mechanical invariant, such as a banned API or generated-file edit | Existing lint/test commands, configuration, hooks, and CI invocation | Propose a deterministic check or repair its execution path. |
| Judgment or ambiguous standards | Applicable conventions and the actual implementation/review workflow | Consider narrow guidance with a clear decision and exceptions. |
| Repeated discovery difficulty | Existing docs, navigation pointers, lesson triggers, and relevant request wording | Propose a precise pointer or refine supported scoped guidance. |
| Expensive tool use | The observed calls, available bounded alternatives, and successful outcomes | Propose a verified cheaper workflow; distinguish measured cost from estimates. |
| Missing diagnostic information | Available logs, tool output, and relevant read access | Propose the smallest useful information-access improvement within the user's authorized scope. |
| Redundant or ineffective instructions | Existing guidance, defaults, exceptions, and evidence of its effect | Consolidate supported guidance or propose removal; length alone does not prove an instruction is unnecessary. |

Keep the inspection scoped to the incident. An absent hook or CI job alone is not evidence of a learning moment. The checklist selects a remedy; it does not relax the promotion gates or authorize implementation work.

For mechanical findings, distinguish an absent check, a check that exists but is unwired or broken, and a working check that covers the mistake. Inspect the relevant command and its hook/CI execution path before treating the behavior as already enforced. State whether execution and coverage were verified or only configuration was inspected. Prefer repairing existing enforcement to duplicating it in prose or another check. Where verification is unavailable, retain the gap rather than asserting prevention.

Recommendations can be reported without creating a lesson or evidence record. A proposed check, pointer, or access change is a deferral when implementation falls outside the user's authorized scope; the retrospective alone grants no implementation authority. An unimplemented remedy is not verified guidance. Activate a lesson only if its own safe action passes every gate independently of the proposed work.

## Evidence and promotion gates

Preserve only a compact contrast: situation, attempted behavior, feedback, corrected behavior, and outcome. A candidate survives only when all are true:

1. Traceable evidence exists.
2. It changes a future behavior or decision.
3. It is non-default and specific to this project or this user's work on the project.
4. It is likely to recur, or forgetting has meaningful cost.
5. Trigger, narrow stable scope, and safe action are clear.
6. It generalizes only one conceptual level beyond the incident.
7. It is reconciled with existing lessons, instructions, workflows, and enforcement.
8. Memory is appropriate; an existing mechanical check does not already enforce it. If always-visible project instructions already state the same trigger and action, treat the finding as duplicate guidance unless it adds a distinct decision rule.

Activate only when the corrected behavior succeeded or authoritative repository evidence confirms it, authority/scope/delivery are unambiguous, and no conflict remains. Evidence-bearing uncertainty becomes `candidate`. Unresolved contradiction becomes a new `conflicted` lesson with `delivery: none`; targeted active guidance remains untouched.

Generic advice, ordinary success, praise, weak lexical similarity, expected probing failures, transient retries, and task-specific state create no record.

## Reconciliation

Classify findings as `new`, `duplicate`, `refines`, `extends`, `conflicts`, `supersedes`, or `obsoletes`.

- Add provenance to a duplicate; do not create another lesson.
- A changed interpretation of the same recovery source requires explicit acceptance through an evidence patch.
- A changed recovery endpoint requires duplicate/new reconciliation; never infer identity from one shared endpoint.
- Supersede only with explicit validated correction and a valid active replacement in the same transaction.
- Conflict activation is valid only when the final manifest retires/supersedes the contradictory guidance or proves the final scopes disjoint. Prose-only compatibility is insufficient.
- Preserve `conflict_history` through retirement, reactivation, and replacement chains.

## Privacy and retention

Persist no raw conversation, transcript item, normalized event stream, command, output, scan cursor, failure category, secret, or unrelated narrative. Recovery evidence may retain only sanitized contrast, bounded behavior delta, stable source-event IDs, fingerprints, and analyzer provenance.

Replace the resolved project and home prefixes with `<project>` and `<home>`. Reject remaining absolute paths, credentials, emails, control characters, and high-entropy prose values. Opaque source IDs may use UUID-like values.

## Usage semantics

Measure only lessons active before the current visible session whose paths, operations, or triggers clearly occurred.

- Increment `eligible_sessions` and pair it with `last_eligible_at`.
- Increment `violations` and `last_violated_at` when attempted behavior opposed the lesson.
- Also increment `repeat_corrections` when feedback repeated the same correction.
- Otherwise increment `confirmations` and `last_confirmed_at` only when following the lesson produced an observed successful outcome.

The originating session is provenance, not usage. Historical mining never increments usage. Do not infer retrieval, application, helpfulness, or outcome attribution from matching behavior.

## Reporting

For a no-op with no actionable recommendations, report that no evidence-backed lesson was found and no files changed. Otherwise report IDs, authority, reconciliation, status/delivery, usage deltas, changed files, and unresolved conflicts. When no canonical write was made, say so even if recommendations remain.

For each actionable deferral, give the observed problem, proposed remedy, supporting evidence, expected benefit, and verification gap. Prioritize by consequence and supported recurrence, distinguishing observed outcomes from estimated benefits. Recommendations are proposals, not new instructions or automatic lesson promotions.
