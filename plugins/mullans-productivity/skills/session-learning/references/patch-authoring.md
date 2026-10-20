# Lesson Authoring

First apply decision policy. Read the section for your operation and Finish; load Advanced update contracts for manifests or scope/conflict/usage/equivalence changes. `<helper>` means `<skill-root>/scripts/session_learning.py`; `<root>` is the project. Use command `--help` for arguments, enum values, and typed-operation contracts.

## Find and inspect

```text
python <helper> search experiment providers --root <root> --authority both --summary --json
python <helper> read lesson.experiment-providers --root <root> --authority project --fields statement,scope,safe_path,exceptions
```

Search is token-ranked, not an exact quoted-phrase match. Filter/page summaries until reconciliation is supported, then use the matched ID/authority. Select needed fields; omit `--fields` for the full record or add `--type evidence` for evidence. Expand truncated content before relying on it.

`read` supplies the logical `path` and full original record's `expected_sha256`, even with selected fields. Use that hash unchanged. Reading does not audit or recover interrupted transactions.

## Submit confirming evidence

Assume `lesson.experiment-providers` already requires separate providers. Save `evidence.json`:

```json
{
  "schema_version": 2,
  "record_type": "evidence",
  "id": "evidence.provider-confirmation",
  "authority": "project",
  "session_id": "session-provider-review",
  "signal": "explicit_user_correction",
  "situation": "A perk console experiment was queued.",
  "attempted_behavior": "Queued a replacement base-console module.",
  "feedback": "Keep experiments separate; perk experiments use their own provider and perk prefix.",
  "corrected_behavior": "Cancelled the untouched queue entry.",
  "outcome": "The replacement was cancelled; perk implementation remains pending.",
  "created_at": "2026-10-20T12:00:00Z"
}
```

```text
python <helper> submit-evidence --root <root> --authority project --lesson lesson.experiment-providers --evidence evidence.json
python <helper> audit --root <root> --authority both
```

This atomically saves evidence and confirms the lesson by appending provenance; guidance/usage stay unchanged. No caller hash or full lesson read is needed. For existing same-authority evidence use `--evidence-id evidence.provider-confirmation`. Identical submissions are no-ops; conflicting content under an existing ID is rejected.

## Update one lesson

Read the affected guidance, then save `patch.json` using `read`'s hash:

```json
{
  "expected_sha256": "<expected_sha256>",
  "intent": "add_exception",
  "operations": [{"op": "append_exception", "value": "A finalized experiment may be integrated after an explicit user request."}]
}
```

```text
python <helper> update-lesson lesson.experiment-providers patch.json --root <root> --authority project
python <helper> audit --root <root> --authority both
```

Only pure provenance-only `confirm` may omit a hash; usage/equivalence changes also require it. On a stale hash, reread affected fields and reconcile before retrying. `update-lesson --help` gives required/optional operations and value shapes; `append_triggers` alone is not a scope update. Omit unused optional fields.

## Create one lesson

Choose authority/delivery through [authority-routing.md](authority-routing.md). Save `lesson.json`:

```json
{
  "id": "lesson.perk-provider",
  "title": "Perk experiment provider",
  "statement": "Perk experiments use a separate provider and the perk prefix.",
  "kind": "guardrail",
  "status": "candidate",
  "scope": {"type": "paths", "paths": ["src/perks/**"]},
  "triggers": ["perk experiments"],
  "anti_pattern": ["Replacing the base console for perk experiments."],
  "safe_path": ["Use the separate perk provider and prefix."],
  "exceptions": [],
  "delivery": {"mode": "none"}
}
```

```text
python <helper> create-lesson lesson.json --root <root> --authority project --evidence-id evidence.provider-confirmation
python <helper> audit --root <root> --authority both
```

Use `--evidence evidence.json` instead to create evidence atomically. The command derives provenance and fills zero usage, timestamps, missing relationship lists, unset delivery fields, and initial conflict history from any supplied targets. Supply delivery-specific fields when applicable; status/delivery remain explicit choices subject to promotion policy. Existing lesson IDs are rejected. Use `apply-manifest` for coordinated changes, maintenance, or supersession, and [draft-review.md](draft-review.md)'s `accept-draft` for drafts.

## Coordinate records (alternative to the creation command)

Instead of running `create-lesson`, this complete `manifest.json` confirms the existing lesson and creates a related candidate using the same evidence. Replace the hash from `read`. Implementation is pending, so delivery is `none`; activate only after decision policy's promotion gate passes.

```json
{
  "manifest_schema_version": 3,
  "origin": "current_session",
  "changes": [
    {
      "path": ".session-learning/lessons/lesson.experiment-providers.json",
      "lesson_patch": {
        "expected_sha256": "<expected_sha256>",
        "intent": "confirm",
        "operations": [{"op": "append_provenance", "value": {
          "evidence_id": "evidence.provider-confirmation",
          "signal": "explicit_user_correction"
        }}]
      }
    },
    {
      "path": ".session-learning/lessons/lesson.perk-provider.json",
      "json": {
        "record_type": "lesson",
        "id": "lesson.perk-provider",
        "authority": "project",
        "equivalence_key": null,
        "conflict_targets": [],
        "conflict_history": [],
        "title": "Perk experiment provider",
        "statement": "Perk experiments use a separate provider and the perk prefix.",
        "kind": "guardrail",
        "status": "candidate",
        "scope": {"type": "paths", "paths": ["src/perks/**"]},
        "triggers": ["perk experiments"],
        "anti_pattern": ["Replacing the base console for perk experiments."],
        "safe_path": ["Use the separate perk provider and prefix."],
        "exceptions": [],
        "delivery": {
          "mode": "none", "host": null, "path": null,
          "instruction_path": null, "enforcement_target": null
        },
        "provenance": [{"evidence_id": "evidence.provider-confirmation", "signal": "explicit_user_correction"}],
        "relationships": {"supersedes": [], "related": ["lesson.experiment-providers"]},
        "usage": {
          "eligible_sessions": 0, "violations": 0, "repeat_corrections": 0, "confirmations": 0,
          "last_eligible_at": null, "last_violated_at": null, "last_confirmed_at": null
        },
        "timestamps": {"created_at": "2026-10-20T12:00:00Z", "updated_at": "2026-10-20T12:00:00Z"}
      }
    }
  ]
}
```

```text
python <helper> read lesson.experiment-providers --root <root> --authority project --fields provenance
python <helper> apply-manifest manifest.json --root <root> --authority project
python <helper> audit --root <root> --authority both
```

If evidence is not saved yet, include it in the same manifest as `{"path": ".session-learning/evidence/<id>.json", "json": <complete-evidence-record>}`. Omit that entry for existing evidence. Manifest-created lessons require complete records as above; the runtime stamps their `schema_version` and writing `version`. Existing lessons accept `lesson_patch`, not full replacement. Existing recovery evidence requires the `evidence_patch` in [history-mining.md](history-mining.md).

## Advanced update contracts

- For grounded maintenance/consolidation, read [reflection.md](reflection.md) before authoring. Maintenance requires schema 3, `origin: maintenance`, and reviewed `expected_store_revision`. Individual patches also retain their record hashes. Schema 2 manifests cannot carry revision/receipt fields.
- Optional `operation_id` makes identical manifest replay return committed IDs; changed content under the same ID fails.
- Operations are unique and applied in canonical order. Arbitrary JSON paths, required-field deletion, and cross-authority references are invalid.
- `narrow`/`extend` require provable literal set containment or the supported repository transition. Use `revise_scope` for paths/subsystem changes or unprovable glob containment.
- Conflict activation requires historical targets to be retired/superseded or scopes proven disjoint. Proof supports exact normalized paths and trailing `/**` prefixes; repository scope overlaps everything. Unsupported globs/aliases/symlink uncertainty cannot prove disjointness. Clearing current targets preserves `conflict_history`; replacements inherit obligations.
- Usage updates follow decision policy: counters only increase with paired timestamps; historical/mined-source and maintenance writes reject usage updates.
- `equivalence_update` is `{value, rationale}`: a lowercase stable key or null, with a non-empty reconciliation rationale. Active keys remain unique within an authority.

## Finish

Writes validate the complete proposed state and roll back on failure. A canonical no-op creates no transaction journal or canonical byte changes; local activity counts may still update. Use compact changed-ID/validation receipts; audit separately after success. A stored hook error does not mean the current write failed. Check audit exit status/structural results, and use `audit --json` for details.
