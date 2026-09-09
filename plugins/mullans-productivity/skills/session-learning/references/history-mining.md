# Historical Recovery Mining

Read this reference before running `mine-history` or authoring `recovery_pair` evidence. Mining is a read-only hypothesis generator; the retrospective remains the authoring boundary.

## Command and status

```text
python <skill-root>/scripts/session_learning.py mine-history --host codex --root <root> [--home-dir <home>] [--since <ISO-date>] [--session <id>] [--json] [--page <n>] [--report-filter actionable|new|reinterpretation] [--detail <candidate-id>] [--expect-scan <hash>]
```

`complete`, `failed`, and `degraded` exit 0, 1, and 2 respectively. Degraded output may retain fully supported candidates, but it never asserts completeness. Narrow the scan with `--since` or `--session` when a scan budget is reached; pagination cannot recover unscanned history.

The Codex scanner reads only `~/.codex/sessions/**/*.jsonl` and `~/.codex/archived_sessions/**/*.jsonl`. A session matches when its resolved `cwd` equals the requested root or is its descendant. A parent or sibling does not match. Claude history scanning is not implemented.

## Conservative recovery contract

A candidate requires an observable failure, one to three ordinal-sorted repair events, and a later corresponding success. Up to four supporting events may occur strictly between failure and verification. All roles must be unique, belong to one session, use the same operation/task identity, and fit within the bounded proximity window.

Every user-authored item is a `user_boundary`. Malformed, truncated, or unknown consequential records are causal barriers. Dependency installation or another stronger state-changing explanation breaks attribution. Inert allowlisted records may be skipped. Completed candidates on either side of a barrier survive; an incomplete sequence does not.

Behavior changes use this bounded shape:

```json
{
  "type": "add|remove|replace|reorder",
  "before": [{"operation": "run_command", "strategy": "direct"}],
  "after": [{"operation": "run_command", "strategy": "targeted"}]
}
```

Each side contains at most three observed allowlisted steps. `add` has an empty `before`; `remove` has an empty `after`; `replace` has two different non-empty sides; `reorder` contains the same unique steps in a different order. Never invent an unobserved step.

## Identity and interpretation

`source_fingerprint` hashes `(host, session_id, failure_event_id, verification_event_id)`. The evidence ID uses its first 20 hex characters. Repair/support roles are not source identity.

`content_fingerprint` hashes the sanitized contrast, every causal role, and the behavior delta. `analyzer_version` is separate provenance. Therefore:

- same source and content: unchanged no-op, even with a newer analyzer;
- same source and different content: `reinterpretation_required`;
- a shared endpoint with changed endpoints: `source_reconciliation_required`;
- the same source routed to another authority: authority reconciliation required.

Accept reinterpretation only through an atomic evidence patch after inspecting full candidate detail. Rejecting it leaves evidence and usage unchanged.

## Budgets and reports

The scanner starts a monotonic 30-second deadline before discovery. Limits are 10,000 directory entries, 4 KiB metadata per file, 1 MiB per JSONL record, 16 MiB per session, 64 MiB total input, 50 matching sessions, 20,000 normalized events, 100 candidates, and 100 diagnostics. Filesystem calls are synchronous and are checked between bounded operations; the deadline is not an OS-level preemption guarantee.

Compact output is capped at 16 KiB with 20 candidates and 20 diagnostics per page. Detail output and the overall report cap are 256 KiB. Limits are checked before accepting more work; a terminal diagnostic reserves the final diagnostic slot. Budget interruption produces `degraded` and retains only completed candidates.

Compact summaries contain candidate ID, inferred authority, behavior delta, verified outcome, and reason codes. Detail adds sanitized contrast, causal roles, fingerprints, and analyzer version. Exact matches appear only as counts. Filters and pages affect report visibility, not scan status or counts. A continuation reruns the scan and `--expect-scan` rejects changed histories, existing evidence, or analyzer version. No cursor or scan cache is persisted.

## Authoring flow

1. Stop on `failed`; disclose every `degraded` limitation.
2. Review compact actionable summaries across all relevant pages.
3. Request detail only for candidates that pass the mandatory decision policy.
4. Compare against both authorities, instructions, and enforcement.
5. Discard transient, weak, duplicate, or ambiguous findings.
6. Build sanitized evidence and either a complete new lesson or a typed lesson/evidence patch.
7. Apply one manifest to the selected authority and validate both authorities.

Do not persist category hints, report pages, scan fingerprints as cursors, or normalized events.
