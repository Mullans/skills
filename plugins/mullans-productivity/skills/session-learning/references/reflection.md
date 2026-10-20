# Explicit Reflection

Use only for requested review/maintenance of existing guidance; structural `audit` does not assess usefulness.

## Review

1. Read [decision-policy.md](decision-policy.md). Apply its evidence, privacy, reconciliation, and reporting gates.
2. Run `activity` once. Treat counts as investigation prompts, not causal findings or effectiveness scores; disclose unavailable/provisional coverage.
3. Run `reflection-context --authority both --page 1`, optionally `--query <topic>`. Retain `revisions`. Stop authoring when `health.can_author` is false and inspect `audit --authority both --json`; follow [schema-compatibility.md](schema-compatibility.md) for version issues.
4. Read affected canonical guidance and each supporting evidence record with `read`; expand truncated fields before relying on them. Inspect relevant conflicts, exceptions, cases, instructions/projections, and actual enforcement coverage.
5. Prioritize contradictions, repeated corrections, candidates, redundancies, unclear actions/scopes, and delivery cost. Page through the requested scope using the original `--expect-revisions '<JSON object>'`. A mismatch requires fresh review. Record unread material or scope limits.

## Apply maintenance

Read [patch-authoring.md](patch-authoring.md) before writing and [authority-routing.md](authority-routing.md) before routing changes. Use `origin: maintenance`, manifest schema 3, and `expected_store_revision` from the reviewed authority. Each patch also needs its record hash. `update-lesson` supports the same guards for a single lesson. After changing an authority, take a fresh snapshot before further changes.

For consolidation, use one same-authority manifest:

1. Select an active survivor, or create an active replacement supported by existing sanitized evidence. Carry forward still-valid guidance and exceptions; cite current supporting evidence, not disproved support.
2. For a survivor, use `replace_action` with required `replace_safe_path` and `append_relationship` values of type `supersedes` naming each source. Only this schema-3 maintenance combination additionally permits `append_provenance`, `append_exception`, and `append_relationship` values as lists of 1–100 items. Other intents keep ordinary value shapes.
3. Include one `supersede` patch per source: `set_status` to `superseded` and `set_delivery_none`. Link a newly created replacement through `relationships.supersedes` instead. Retain source records, evidence, exceptions, and usage as history; copying them wholesale into the replacement is unnecessary.
4. Preserve inherited conflict obligations and satisfy the authoring reference's final-state proof before activation. Leave ambiguous corrections conflicted. Start new replacements with zero usage rather than combining source counters.

Maintain only conclusions supported by existing evidence. New observations/evidence, draft acceptance, history mining/rescans, usage increments, and schema migration belong outside reflection. Do not retire solely for age or low exposure. Report cross-authority contradictions with authority-qualified IDs; preserve retrieval until consequential ambiguity is resolved.

## Finish

Run `audit --authority both` separately. Report changed guidance, support, preserved exceptions/conflicts, coverage limits, and unresolved findings in proportion to the review. For a no-op, submit an empty guarded maintenance manifest. Changes to capture/reminders/configuration/skill implementation need a separate request under `SKILL.md`'s authorization boundary.
