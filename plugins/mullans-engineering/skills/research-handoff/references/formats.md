# Handoff formats

Read when creating or adapting handoff infrastructure. Existing project conventions
take precedence. This reference owns the default formats for both research handoff
and research setup; setup can prepare them without performing a closeout.

## Current-work index

Find an existing index or create root `next-handoff.md` from the
[index template](../assets/next-handoff.md). Link it from an existing root README
or entry page when available. Creating a handoff needs no broader documentation tree.

| Column | Meaning |
| --- | --- |
| Topic | Short human-readable objective or workstream name |
| Status | Current condition: in progress, paused, waiting, or blocked; name the dependency when waiting or blocked |
| Follow-up document | Relative Markdown link to the actual continuation snapshot |
| Next action | One concrete step and its immediate prerequisite |

Use one row per pending workstream. Keep a new index empty until actual work needs
continuation; omit illustrative rows. The index owns current status and action,
not findings or resource claims. Snapshots retain their dated context.

## Snapshot and lifecycle

Find a local template or create `docs/handoffs/TEMPLATE.md` from the
[snapshot template](../assets/handoff.md). Adapt fields to the project.

Without an existing lifecycle, write unique stable snapshots at
`docs/handoffs/<topic>-<YYYYMMDD>[-sequence].md`. The date is snapshot creation;
append a sequence for collisions. Resuming does not move a snapshot. A fresh
snapshot replaces the current index pointer, preserving history.

Update only the selected workstream's row. Remove it when no follow-up remains
and its outcome has another discovery route. Leave completed snapshot history
intact. A project with an existing active/archive procedure keeps that procedure.

## Publication coordination

For concurrent index writers, use the project's existing serialized update method
and reread/merge the selected row within its critical section. An atomic replacement
protects file integrity but does not prevent a stale read from losing another row.
Do not treat handoff status as a lock. If safe serialization is unavailable, retain
the valid snapshot and report its path with routing pending; do not silently
overwrite concurrent changes. Routine single-writer closeout needs no new locking
system.

## Links and portability

Resolve index links from the index and snapshot links from the snapshot, not from
these assets. Generated files point to local project records rather than installed
skill files. If the project has no records yet, the snapshot can hold its immediate
context. Find or create the minimal structure without requiring research setup,
Git, a findings taxonomy, or a resource ledger.
