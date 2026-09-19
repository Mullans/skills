# Typed Patch Authoring

Read this reference before any canonical mutation. Ordinary semantic/runtime changes use typed patches. A future incompatible schema migration requires a distinct version-specific privileged mechanism and is not constrained to these intents.

## Manifest boundary

Apply one authority-scoped manifest:

```json
{
  "manifest_schema_version": 2,
  "origin": "current_session|historical_mining|maintenance",
  "changes": []
}
```

New lessons and evidence are complete JSON records. The runtime stamps each new lesson with the installed `schema_version` and skill `version` before writing it. Existing lessons reject full replacement and require `lesson_patch`; existing recovery evidence requires `evidence_patch`. Every update includes `expected_sha256`, computed from canonical pre-update JSON. One mismatch rejects the entire manifest before writing.

An OS-managed writer lock covers recovery, reads, hash checks, proposed-state validation, journal creation, writes, derived-state rebuild, validation, commit, and rollback. Windows uses a named mutex keyed by normalized root and authority. POSIX uses `flock` on the resolved project directory and intentionally serializes both authorities. No persistent lock file is created.

## Lesson patch

```json
{
  "expected_sha256": "<sha256>",
  "intent": "replace_action",
  "operations": [{"op": "replace_safe_path", "value": ["step"]}],
  "usage_update": null,
  "equivalence_update": null
}
```

Omit unused optional fields. Operations are unique and applied in canonical order regardless of manifest order.

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

Named operations are `append_provenance`, `replace_statement`, `replace_scope`, `append_triggers`, `append_exception`, `replace_anti_pattern`, `replace_safe_path`, `set_status`, `set_delivery`, `set_delivery_none`, `set_conflict_targets`, `clear_conflict_targets`, and `append_relationship`. Arbitrary JSON paths, duplicate operations, required-field deletion, and cross-authority references are invalid.

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
