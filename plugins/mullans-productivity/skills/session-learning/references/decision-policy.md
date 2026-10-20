# Session Learning Decision Policy

Apply these gates to retrospectives and reflection. Use visible session evidence or supplied summaries; do not reconstruct missing history or ask the user to retell it.

## Select evidence and a remedy

Prefer explicit corrections/conventions, then decisive tests/runtime/CI/review results, verified non-obvious discoveries or workflows, repeated observations, and lastly analyzer inference. Treat analyzer interpretations as hypotheses, not verification. Current-session and historical findings use the same gates.

| Observed friction | Inspect | Prefer |
| --- | --- | --- |
| Mechanical invariant | Check implementation and its actual lint/test/hook/CI invocation | Repair enforcement or propose a deterministic check |
| Ambiguous standards | Conventions and review workflow | Narrow decision guidance |
| Discovery difficulty | Existing docs, pointers, triggers | A precise pointer or scoped refinement |
| Expensive tools | Observed calls and verified bounded alternatives | A cheaper verified workflow |
| Missing information | Available diagnostics and access | The smallest useful diagnostic/access improvement |
| Redundant guidance | Existing rules and their observed effects | Consolidation or removal |

Keep inspection scoped to the incident. Distinguish absent, broken/unwired, and effective enforcement; verify execution and coverage before calling a mistake already prevented. Where only configuration was inspected, retain that verification gap. An absent check alone is not a lesson.

Recommend improvements without creating memory when implementation is the appropriate remedy. A retrospective does not authorize building proposed enforcement. An unimplemented fix cannot serve as verified guidance; any independently valid lesson must pass the gates below.

## Evidence and promotion gates

Preserve a compact contrast: situation, attempted behavior, feedback, corrected behavior, outcome. Accept guidance only when all hold:

1. Evidence is traceable.
2. It changes a future behavior or decision.
3. It is non-default and specific to this project or user's work here.
4. Recurrence or the cost of forgetting justifies retention.
5. Trigger, narrow stable scope, and safe action are clear.
6. It generalizes at most one conceptual level beyond the incident.
7. It is reconciled with existing lessons, instructions, workflows, and enforcement.
8. Memory adds a distinct rule beyond already-visible instructions or working enforcement.

Activate only after the corrected behavior succeeds or authoritative repository evidence confirms it, with clear authority/delivery and no unresolved conflict. Preserve evidence-bearing uncertainty as `candidate`. Record unresolved contradictions as a new `conflicted` lesson with delivery `none`; leave active guidance untouched.

Generic advice, ordinary success, praise, weak lexical similarity, expected probing failures, transient retries, and task state create no record.

## Reconciliation

Classify each finding as `new`, `duplicate`, `refines`, `extends`, `conflicts`, `supersedes`, or `obsoletes`.

- Confirm duplicates by appending provenance, not another lesson.
- For changed interpretation of the same recovery source, follow [history-mining.md](history-mining.md)'s evidence patch. Changed endpoints require new/duplicate reconciliation; a shared endpoint does not establish identity.
- Supersede only with validated correction and an active replacement in the same transaction. Follow [reflection.md](reflection.md) for maintenance consolidation.
- Activate conflicting guidance only when the final state retires/supersedes contradictory guidance or proves scopes disjoint. Preserve `conflict_history` across lifecycle changes and replacements. Prose alone cannot prove compatibility.

## Privacy

Persist sanitized contrasts, bounded behavior deltas, stable source-event IDs, fingerprints, and analyzer provenance only. Exclude raw conversations, normalized events, commands, outputs, logs, scan cursors, failure categories, secrets, and unrelated narrative.

Replace project/home prefixes with `<project>`/`<home>`. Reject remaining absolute paths, credentials, emails, control characters, and high-entropy prose. Opaque source IDs may be UUID-like.

## Usage

Measure only lessons active before this visible session whose paths, operations, or triggers clearly occurred:

- Increment `eligible_sessions` with `last_eligible_at`.
- Increment `violations` with `last_violated_at` for opposed behavior.
- Also increment `repeat_corrections` when feedback repeats the correction.
- Otherwise increment `confirmations` with `last_confirmed_at` only after following guidance produces observed success.

Originating-session evidence is provenance, not usage. Historical mining never increments usage. Matching or retrieval alone proves no application, helpfulness, or outcome.

## Report proportionately

State the requested outcome, relevant IDs/authority, and unresolved issues. For a no-op, say “no canonical changes” and why, such as duplicate evidence; an unchanged store does not mean no valid lesson exists. Include changed guidance, usage deltas, or review coverage when relevant.

For actionable recommendations, give the problem, remedy, supporting evidence, expected benefit, and verification gap concisely. Distinguish measured outcomes from estimates; expand evidence/uncertainty detail only when needed to assess the decision. Recommendations remain proposals, not new instructions.
