# Lesson Authoring

Read this reference before canonical authoring, after the decision policy's evidence and reconciliation gates. Commands below use `<helper>` for `<skill-root>/scripts/session_learning.py` and `<root>` for the project. Command `--help` owns arguments and typed-operation contracts.

## Find and inspect

```text
python <helper> search experiment providers --root <root> --authority both --summary --json
python <helper> read lesson.experiment-providers --root <root> --authority project --fields statement,scope,safe_path,exceptions
```

Search returns bounded summaries; use filters or the next page when necessary. Terms are token-ranked, not exact quoted phrases. Once a match supports reconciliation, use its ID and authority instead of broadening search. Read only needed fields, or omit `--fields` for the full lesson; `--type evidence` reads one supporting evidence record. Truncated summaries cannot support decisions about omitted content.

`read` returns the logical `path` and `expected_sha256` of the full original record even when selecting fields. Use that hash unchanged for guarded edits. Reading does not audit, recover interrupted writes, or load related records.

## Submit confirming evidence

Assume the existing project lesson `lesson.experiment-providers` already requires separate console providers. Save this sanitized current-session evidence as `evidence.json`:

```json
{
  "schema_version": 2,
  "record_type": "evidence",
  "id": "evidence.provider-confirmation",
  "authority": "project",
  "session_id": "session-provider-review",
  "signal": "explicit_user_correction",
  "situation": "A new console experiment was queued.",
  "attempted_behavior": "Queued a replacement base-console module.",
  "feedback": "Use a separate provider and experiment prefix.",
  "corrected_behavior": "Cancelled the untouched queue entry.",
  "outcome": "The base-console replacement was cancelled; implementation remains pending.",
  "created_at": "2026-10-20T12:00:00Z"
}
```

```text
python <helper> submit-evidence --root <root> --authority project --lesson lesson.experiment-providers --evidence evidence.json
python <helper> audit --root <root> --authority both
```

This atomically saves the evidence and appends its reference to the lesson's provenance through a `confirm` patch. Guidance and usage remain unchanged; no caller hash or full lesson read is needed. Use `--evidence-id evidence.provider-confirmation` instead of `--evidence` to link evidence already in that authority. Identical submissions are no-ops; different content under an existing evidence ID is rejected. Historical evidence still requires [history-mining.md](history-mining.md).

## Update one lesson

After reading the affected guidance, save a typed patch as `patch.json`, replacing the hash placeholder with `read`'s `expected_sha256`:

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

`update-lesson --help` lists required/optional operations and value shapes. Existing intent rules apply: `append_triggers` alone is not a scope update. Every edit requires a hash except a pure provenance-only `confirm` without usage or equivalence changes. A stale hash rejects the write; read the affected fields again and reconcile before retrying. Maintenance also requires `--origin maintenance --expected-store-revision <reviewed-token>` from [reflection.md](reflection.md).

Use `apply-manifest` below for new lessons and coordinated changes; [draft-review.md](draft-review.md)'s `accept-draft` remains the route for draft acceptance. Convenience commands do not replace their evidence or review gates.

## Manifest boundary

For advanced authoring, apply one authority-scoped manifest. This complete confirmation manifest reuses the evidence above. Obtain the current hash with `read`, substitute it below, and save as `manifest.json`:

```json
{
  "manifest_schema_version": 3,
  "origin": "current_session",
  "changes": [{
    "path": ".session-learning/lessons/lesson.experiment-providers.json",
    "lesson_patch": {
      "expected_sha256": "<expected_sha256>",
      "intent": "confirm",
      "operations": [{"op": "append_provenance", "value": {
        "evidence_id": "evidence.provider-confirmation",
        "signal": "explicit_user_correction"
      }}]
    }
  }]
}
```

```text
python <helper> read lesson.experiment-providers --root <root> --authority project --fields provenance
python <helper> apply-manifest manifest.json --root <root> --authority project
python <helper> audit --root <root> --authority both
```

To confirm and create a separate narrower lesson together, use a manifest instead of the submission command: add the complete new evidence and lesson as additional `{"path": ".session-learning/evidence/<id>.json", "json": {...}}` and `{"path": ".session-learning/lessons/<id>.json", "json": {...}}` entries. Omit the evidence entry if it already exists. Link the new lesson through provenance and `relationships.related`; retain [authority-routing.md](authority-routing.md)'s record contracts and the decision policy's promotion gates.

Schema 3 maintenance includes `expected_store_revision` from `reflection-context`; the engine checks it under the authority writer lock before applying any change or accepting a no-op. Optional `operation_id` enables idempotent canonical acceptance receipts. Identical replay returns the committed IDs; changed content under the same ID fails. Receipts commit in the same file transaction as canonical changes. Legacy schema 2 manifests remain supported but cannot carry schema 3 guards or receipt fields. Lesson v4 and evidence v2 require no migration for these additions.

New lessons and evidence are complete JSON records. The runtime stamps each new lesson with the installed `schema_version` and skill `version` before writing it. Existing lessons reject full replacement and require `lesson_patch`; existing recovery evidence requires `evidence_patch`. Every update includes `expected_sha256`, computed from canonical pre-update JSON. One mismatch rejects the entire manifest before writing.

Current evidence signals are `explicit_user_correction`, `test_failure`, `runtime_failure`, `ci_failure`, `review_finding`, `durable_user_convention`, `validated_workflow`, `successful_non_obvious_discovery`, and historical `recovery_pair`. Lesson kinds are `guardrail`, `workflow`, `project_knowledge`, `preference`, and `invariant`. An active `workflow` kind requires workflow delivery and its repository-local projection; ordinary dynamically retrieved guidance uses an appropriate non-workflow kind. Inactive delivery has every optional delivery field null. These field contracts do not replace evidence or promotion gates.

## Lesson patch

Omit unused optional fields (`usage_update`, `equivalence_update`). Operations are unique and applied in canonical order regardless of manifest order. Use `update-lesson --help` for operation names and value shapes; the intents below describe the semantic choice.

Schema 3 maintenance may consolidate into an active survivor using `replace_action` plus `append_relationship` entries of type `supersedes`. Only this guarded consolidation permits `append_provenance`, `append_exception`, and `append_relationship` values as bounded lists (1..100 items). Include each source's `supersede` patch in the same manifest. Other intents and legacy manifests retain the original append-value contracts. Source provenance, exceptions and usage remain on the historical source records. A replacement links to those records and cites the evidence supporting its current guidance; it need not copy disproved support or obsolete exceptions. Compatible consolidation carries forward still-valid guidance, while corrective supersession records the validated correction. Structural evidence references, source lifecycle transitions and inherited conflicts remain checked.

| Intent | Allowed purpose |
| --- | --- |
| `measure` | usage only |
| `confirm` | append provenance |
| `narrow`, `extend`, `revise_scope` | replace scope; optionally statement/triggers |
| `add_exception` | append exception; optionally statement |
| `replace_action` | replace safe path; optionally statement/anti-pattern |
| `promote` | candidate to active with valid delivery |
| `resolve_conflict` | conflicted to compatible active or retired |
| `supersede` | active/candidate to superseded with same-manifest active replacement |
| `set_delivery` | change delivery of an active lesson |
| `retire` | active/candidate/conflicted to retired/none |
| `reactivate` | retired to candidate/none |

Arbitrary JSON paths, duplicate operations, required-field deletion, and cross-authority references are invalid.

`narrow` and `extend` require provable literal set containment or the supported repository transition. Use `revise_scope` for `paths`/`subsystem` changes or globs whose containment cannot be proven.

## Conflict proof

Activation validates the complete proposed state. Every retained historical conflict target must be retired/superseded or have a scope proven disjoint.

The conservative proof supports exact normalized resource paths and trailing `/**` directory prefixes only. Repository scope overlaps everything. Nested/identical prefixes overlap. Unsupported globs, aliases, and symlink uncertainty are unknown and therefore cannot authorize activation. Scope/exception edits may establish compatibility; prose alone cannot.

Clearing current `conflict_targets` never clears `conflict_history`. Active replacements inherit the historical obligations of lessons they supersede.

## Usage and equivalence updates

Usage counters may only increase with their paired current-session timestamp. Usage is rejected for `historical_mining`, `maintenance`, or a manifest that adds mined source evidence. It cannot reset counters or change unrelated timestamps.

An `equivalence_update` supplies `{value, rationale}`. The value is a lowercase stable key or `null`; the non-empty rationale records explicit reconciliation. Final-state uniqueness is validated within the authority.

## Evidence reinterpretation

```json
{
  "expected_sha256": "<sha256>",
  "replace_interpretation": {
    "contrast": "<sanitized contrast>",
    "causal_roles": {
      "failure_event_id": "...",
      "repair_event_ids": ["..."],
      "verification_event_id": "...",
      "supporting_event_ids": []
    },
    "behavior_delta": {
      "type": "replace",
      "before": [{"operation": "run_command", "strategy": "direct"}],
      "after": [{"operation": "run_command", "strategy": "targeted"}]
    },
    "analyzer_version": "..."
  }
}
```

The helper performs a bounded read-only rescan of the named Codex session, validates referenced events and causal ordering, and recomputes `content_fingerprint`. Evidence ID, authority, session, signal, source fingerprint, failure endpoint, and verification endpoint are immutable. Repair/support roles may change. Missing or unverifiable source events reject the patch. Analyzer-version-only changes are no-ops.

## Transaction and output

The helper confines every physical target to the selected authority, snapshots original bytes and hashes, atomically replaces files, regenerates derived state, validates the final store, and removes the journal only after success. Failure or interrupted recovery restores the snapshots. A semantic no-op creates no journal and changes no bytes.

Default success output contains changed IDs, authority, status/delivery, validation outcome, usage deltas, and actionable deferrals—not complete records. Request detailed sanitized diffs only when review requires them. Lifecycle CLI commands construct these same patches; they do not bypass the engine.

Run audit separately after success. A stored hook error is a recorded diagnostic, not evidence that the current write failed. Check the audit exit status and structural results; use `audit --json` when details matter. Investigate recorded hook errors separately from confirming the canonical write.
