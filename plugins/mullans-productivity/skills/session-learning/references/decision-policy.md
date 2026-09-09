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

## Evidence and promotion gates

Preserve only a compact contrast: situation, attempted behavior, feedback, corrected behavior, and outcome. A candidate survives only when all are true:

1. Traceable evidence exists.
2. It changes a future behavior or decision.
3. It is non-default and specific to this project or this user's work on the project.
4. It is likely to recur, or forgetting has meaningful cost.
5. Trigger, narrow stable scope, and safe action are clear.
6. It generalizes only one conceptual level beyond the incident.
7. It is reconciled with existing lessons, instructions, workflows, and enforcement.
8. Memory is appropriate; an existing mechanical check does not already enforce it.

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

For a no-op, report that no evidence-backed lesson was found and no files changed. Otherwise report only IDs, authority, reconciliation, status/delivery, usage deltas, changed files, and actionable conflicts or deferrals.
