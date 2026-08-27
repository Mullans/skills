# Session Learning Decision Policy

Use this policy on every explicit retrospective. Canonical knowledge lives in `.agents/learning`; hook delivery is advisory and read-only.

## Inspect and measure

Recover interrupted transactions, read applicable instructions and repository-local skills, inspect existing records and enforcement, then search related lessons:

```text
python <skill-root>/scripts/session_learning.py search --root <project-root> <terms>
```

Measure only lessons active before the session whose paths, operations, or triggers clearly occurred:

- Increment `eligible_sessions` and set `last_eligible_at`.
- Increment `violations` and set `last_violated_at` when attempted behavior opposed the lesson.
- Also increment `repeat_corrections` when feedback repeated the same correction.
- Otherwise, increment `confirmations` and set `last_confirmed_at` only when following the lesson produced a successful outcome.

A lesson's originating session is provenance, not usage. Do not infer retrieval or helpfulness from matching behavior.

## Evidence and promotion gates

Evidence signals are explicit correction, decisive test/runtime/CI result, review finding, durable user convention, validated workflow, or successful non-obvious discovery. Preserve only a compact contrast: situation, attempted behavior, feedback, corrected behavior, and outcome. Never store raw conversation text, logs, secrets, or unrelated narrative.

A candidate survives only when all are true:

1. Traceable evidence exists.
2. It changes a future behavior or decision.
3. It is non-default and project-specific.
4. It is likely to recur, or forgetting has meaningful cost.
5. Trigger, narrow stable scope, and safe action are clear.
6. It generalizes only one conceptual level beyond the incident.
7. It is reconciled with existing lessons, instructions, workflows, and enforcement.
8. Prose or procedural memory is appropriate; an existing mechanical check does not already enforce it.

Auto-promote only when the corrected behavior succeeded or authoritative repository evidence confirms it, scope and delivery are unambiguous, no conflict remains, and the change is limited to project learning/guidance or an established local workflow. One explicit correction may suffice when correction, validation, scope, and consequence are clear.

Evidence-bearing uncertainty becomes `candidate`; unresolved contradiction becomes `conflicted` with existing active guidance untouched. Generic advice, ordinary success, weak observations, and transient state create no record.

Reconcile as `new`, `duplicate`, `refines`, `extends`, `conflicts`, `supersedes`, or `obsoletes`. Add provenance to duplicates instead of creating another lesson. Only explicit validated correction may supersede stale guidance.

## Delivery

Schema-v2 lessons have one authoritative delivery object:

```json
{
  "delivery": {
    "mode": "dynamic",
    "host": null,
    "path": null,
    "instruction_path": null,
    "enforcement_target": null
  }
}
```

- `dynamic`: default for scoped guardrails and contextual knowledge; hooks retrieve it and the compact index is the fallback.
- `static`: broad, safety-critical, or explicitly selected always-visible native instruction projection.
- `workflow`: native repository-local skill, only after exact recurring steps and a successful outcome are established.
- `automation`: proposed mechanical-enforcement target; do not implement it during the retrospective.
- `none`: candidate, conflicted, superseded, retired, or evidence-only material.

Candidates, conflicts, superseded, and retired lessons are never injected or projected as active instructions. A missing static marker is projection drift, not deactivation. Report it; hooks dynamically deliver the lesson when the current host cannot see the projection. Repair with `reconcile-delivery --apply` only during this explicit workflow.

Use the narrowest applicable instruction or workflow path. Every static/workflow projection contains `session-learning:<lesson-id>`. When active dynamic lessons exist, maintain one `session-learning:index` pointer instructing agents to consult `.agents/learning/index.md` only when path, scope, or trigger matches.

Host routing:

1. Prefer known active runtime identity.
2. Inspect applicable `AGENTS.md` and `CLAUDE.md` hierarchies and resolved imports.
3. `activate --host auto` configures only the active host; use `both` only when both are intentionally configured.
4. Claude can share an existing `AGENTS.md` surface only through a verifiable applicable `CLAUDE.md` `@AGENTS.md` import.
5. Never duplicate lesson bodies across both files.
6. Unknown hosts get canonical storage plus the pointer-only manual fallback, not invented hook or instruction conventions.

## Automatic retrieval contract

Hooks never author lessons or read transcripts. `UserPromptSubmit` matches topic and normalized trigger phrases. `PreToolUse` matches paths, operations, and command families. Path/scope overlap ranks first, then exact triggers, operation matches, and title/statement lexical relevance. Weak lexical relevance alone never injects.

Default per-event limits are three lessons and 4,000 characters. A delivered lesson is ineligible until five subsequent user prompts; same-turn events deduplicate it. Compact and resume restoration bypass cooldown. Clear/startup/fork begin without stale relevance. Configuration precedence is project `.agents/learning/config.json`, personal `~/.agents/session-learning/config.json`, then defaults.

```json
{
  "schema_version": 1,
  "retrieval_enabled": true,
  "cooldown_user_prompts": 5,
  "max_lessons_per_event": 3,
  "max_context_characters": 4000,
  "python_path": null
}
```

`python_path` is an optional absolute path to a Python 3 executable, never a command or argument string. Launchers try a usable project-configured path, then a personal path, then the cached fixed launcher and `py -3`, `python3`, or `python`; configured paths are validated on every event and are never stored as cached command text.

Transient state contains only schema version, project/session hashes, prompt sequence, delivered lesson IDs, and timestamps. It stores no prompts, commands, raw paths, or transcripts.

## Records

Store one record per file:

- `.agents/learning/lessons/<lesson-id>.json`
- `.agents/learning/evidence/<evidence-id>.json`
- `.agents/learning/cases/<case-id>.json`
- generated `.agents/learning/index.md`

Use lowercase stable IDs and matching filenames. Lessons use `schema_version: 2`, statuses `candidate|active|conflicted|superseded|retired`, scope, triggers, anti-pattern, safe path, exceptions, delivery, provenance, relationships, timestamps, and usage:

```json
{
  "eligible_sessions": 0,
  "confirmations": 0,
  "violations": 0,
  "repeat_corrections": 0,
  "last_eligible_at": null,
  "last_confirmed_at": null,
  "last_violated_at": null
}
```

Evidence and optional high-value regression cases remain `schema_version: 1`. Evidence fields are `id`, `session_id`, `signal`, `situation`, `attempted_behavior`, `feedback`, `corrected_behavior`, `outcome`, and `created_at`. A regression case records lesson IDs, situation, trap, expected behavior, and creation time.

## Transaction protocol

A no-op retrospective must be filesystem-neutral. Otherwise compute every delta first and submit one manifest to:

```text
python <skill-root>/scripts/session_learning.py apply-manifest --root <project-root> --manifest <file>
```

The helper validates target paths, snapshots hashes and original contents in a transient transaction directory, atomically replaces sibling files, rebuilds the index, validates, and removes the transaction only after success. On failure or interrupted recovery it restores snapshots and reports failure. Never claim success for a partial write.

Run `migrate` before authoring into a v1 store. Use `set-delivery`, `deactivate`, and `reactivate` for lifecycle changes rather than hand-editing projections.

## Report

For a no-op, say no evidence-backed lesson was found and no files changed. Otherwise list lesson IDs, relations, statuses, delivery modes, measurement changes, and informative conflicts or deferrals. Do not retell the session.
