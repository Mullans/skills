# File-based handoff notes

## Qualify and locate

Use for authorized, non-blocking requests belonging to another effort. Blocking
dependencies, findings and changes to the core goal stay in their owning workflows.
Duration alone does not determine whether work is within scope.

Follow the project's annotation permissions and locate the receiving effort's
currently referenced handoff. If none is referenced, report the unrouted request
rather than creating a snapshot. Check for an equivalent existing note.

`Agent request` identifies an agent suggestion; `User request` identifies a human
request. Neither label grants implementation authority. An already-authorized
concrete append needs no second confirmation unless local policy requires it.

## Append

Write a self-contained actionable sentence. Add a Context link only when useful;
do not create another record solely to populate that field.

Run with the project's Python prefix. Command prefix:
`python <skill-root>/scripts/add_handoff_note.py`

| Task or option | Arguments after the prefix |
| --- | --- |
| Append an agent suggestion | `HANDOFF.md --request-type agent --source "Source analysis" --request "Expose the result summary for reuse by the analysis effort."` |
| Record a human request | Use `--request-type user` with the authorized request |
| Useful supporting context | Add `--context "../experiment/RESULT.md"`, relative to the handoff, or a URL |
| Explicit date | Add `--date YYYY-MM-DD` when needed; otherwise the helper uses the machine's local date |
| Preview | Add `--dry-run` when review is needed or project policy requires it |

Resolve `<skill-root>` to this installed skill. The helper creates only the notes
section and reports `added` or `already-present`. Inspect the returned result and
check a newly added Context link where applicable; do not repeat an append merely
to verify it.

The [helper](../scripts/add_handoff_note.py) owns targeted insertion,
deduplication and writer serialization. On failure, inspect the reported cause
before retrying. Investigate the recorded writer before recovering a leftover
lock; do not take over an unexplained lock.

## Receiving and carrying forward

Evaluate notes at pickup or requested review. Keep disposition and resulting work
in the receiving effort's owning record. A note is not dispatch, acceptance or
permission to expand the plan.

Continue originating work without acknowledgement or polling. Coordinate through
project records rather than direct chat discovery or messaging. If an independently
justified replacement handoff is created, carry forward only relevant unresolved
requests.
