# Handoff formats

Use when creating or adapting handoff infrastructure. Preserve equivalent project
conventions; the local lifecycle owns eligibility and operating procedure.

## Infrastructure assets

| Asset | Default project destination | Role |
| --- | --- | --- |
| [Lifecycle](../assets/lifecycle.md) | `docs/handoffs/README.md` | Eligibility, pickup, publication and archiving |
| [Snapshot](../assets/handoff.md) | `docs/handoffs/TEMPLATE.md` | Fields for necessary continuation context |
| [Index](../assets/next-handoff.md) | `next-handoff.md` | Routes pending continuations |

Setup may prepare missing infrastructure without creating a real snapshot or
performing a closeout. Link actual local owners from project navigation.

## Index columns

| Column | Meaning |
| --- | --- |
| Topic | Human-readable objective or workstream |
| Status | Resume condition or dependency, not running progress |
| Follow-up document | Relative link to the selected snapshot |
| Next action | Required unfinished step and immediate prerequisite |

Keep the existing columns and omit illustrative rows from generated indexes.

## Links and portability

Resolve links from the generated file's final location. Project documents link to
local owners rather than installed skill files. When needed context has no owning
record, include that immediate context in the snapshot and identify material gaps.

Keep publication mechanics with existing project helpers. Shared index updates
need serialization and a fresh read/merge; a file's atomic replacement does not
make an earlier read current. Do not introduce another coordination ledger merely
to publish a handoff.
