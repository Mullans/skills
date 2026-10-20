# Historical Recovery Mining

Read before `mine-history`, recovery-pair authoring, or evidence reinterpretation. Mining generates read-only hypotheses; accept them through the retrospective's decision policy.

## Scan and review

```text
python <skill-root>/scripts/session_learning.py mine-history --host codex --root <root> --json
```

| Status / exit | Action |
| --- | --- |
| `complete` / 0 | Review the bounded relevant results |
| `failed` / 1 | Stop; no trustworthy scan result |
| `degraded` / 2 | Review only completed candidates and disclose every limitation |

Use `--since` or `--session` to narrow budget-limited scans; pages cannot recover unscanned history. Codex scans current/archived sessions for this root and descendants, not parents/siblings. Claude scanning is unsupported.

Review relevant summary pages, then request `--detail <candidate-id>` for promising findings. Inspect sanitized contrast, causal roles, and behavior delta. Filters/pages change visibility, not scan completeness; an empty page proves no absence. Continuations rerun the scan: retain `--expect-scan <hash>` and restart review if it changes.

## Evidence contract

A recovery requires observed failure, one to three ordered repair events, and corresponding later success in one session/task identity. Up to four unique supporting events may fall strictly between failure and verification. User messages, malformed/unknown consequential records, or stronger alternative explanations break attribution. Never fill causal gaps.

Behavior deltas use:

```json
{
  "type": "replace",
  "before": [{"operation": "run_command", "strategy": "direct"}],
  "after": [{"operation": "run_command", "strategy": "targeted"}]
}
```

Each side permits at most three observed allowlisted steps. `add` has empty `before`; `remove` has empty `after`; `replace` has different non-empty sides; `reorder` has the same unique steps reordered.

Keep supplied fingerprints unchanged. A new recovery evidence ID is `evidence.recovery.` plus the first 20 characters of `source_fingerprint`; do not recompute hashes. Preserve the source session identity.

| Comparison | Reconcile as |
| --- | --- |
| Same source/content, even newer analyzer | Unchanged no-op |
| Same source, changed content | `reinterpretation_required` |
| Shared endpoint but changed endpoints | `source_reconciliation_required` |
| Same source, another authority | Authority reconciliation |

## Reinterpret existing evidence

Inspect full candidate detail before accepting a changed interpretation. Use `read <evidence-id> --type evidence` for its current hash, then place this `evidence_patch` under that record's logical path in an [authoring manifest](patch-authoring.md):

```json
{
  "expected_sha256": "<sha256>",
  "replace_interpretation": {
    "contrast": "<sanitized contrast>",
    "causal_roles": {
      "failure_event_id": "<failure>",
      "repair_event_ids": ["<repair>"],
      "verification_event_id": "<verification>",
      "supporting_event_ids": []
    },
    "behavior_delta": {
      "type": "replace",
      "before": [{"operation": "run_command", "strategy": "direct"}],
      "after": [{"operation": "run_command", "strategy": "targeted"}]
    },
    "analyzer_version": "<analyzer-version>"
  }
}
```

Evidence ID, authority, session, signal, source identity, failure endpoint, and verification endpoint are immutable. Repair/support roles may change. The helper rescans referenced events and causal ordering; missing or unverifiable sources reject the patch. Analyzer-version-only changes are no-ops. Rejection preserves evidence and usage.

For accepted findings, follow [decision-policy.md](decision-policy.md) and [patch-authoring.md](patch-authoring.md): reconcile both authorities/instructions/enforcement, preserve sanitized evidence, write to one authority, and audit both. Do not persist report pages, category hints, scan cursors, or normalized events; historical mining never increments usage.
