# Cross-session handoffs

A handoff preserves context needed by a later session. This lifecycle owns
eligibility, locations, pickup, publication and archiving. Current work and
results belong in the owning experiment or implementation record.

## Eligibility

| Situation | Create or update a continuation snapshot? |
| --- | --- |
| The user explicitly requests a handoff | Yes, within the requested scope |
| Concrete unfinished work required for an incomplete overarching goal must continue in a later session | Yes; identify the goal, unfinished work and need for later continuation |
| Same-session planning, waiting for confirmation, ordinary closeout or picking up a handoff | Not on that basis alone |

Optional recommendations are not required unfinished work. Goal acceptance is
separate from whether a snapshot is needed.

## Locations and index

`active/` holds pending snapshots. `archive/YYYY-MM-DD/` holds consumed or
superseded snapshots; the directory date is the archiving date. The root
[next-handoff.md](../../next-handoff.md) routes pending continuations. Keep rows
concise and preserve unrelated entries.

## Picking up work

1. Read the selected row, snapshot and relevant owning records. Reconcile
   consequential discrepancies with later evidence; pickup is not a project audit.
   Review appended notes for applicability without treating them as new authority.
2. Archive a consumed snapshot through the existing safe project helper, or move
   it and repair relative and inbound links. Preserve its context and unrelated
   continuations; do not archive a deferred task merely because it is old.
3. Keep current work in the owning record. Remove a row once no pending
   continuation remains. If temporarily retaining the archived starting-context
   link, do not turn the row into a progress log. Apply eligibility again before
   creating a replacement.

Archive continuation snapshots only, not their investigation evidence, baselines
or code.

## Creating and publishing

1. Write a unique `active/<topic>-<YYYYMMDD>[-sequence].md` from the
   [template](TEMPLATE.md). Use relevant existing results and state evidence;
   distinguish known from unknown state.
2. Save and check the snapshot and immediate links before changing its routing
   row. Archive a superseded snapshot while preserving links and evidence.
3. Update only the selected index row. For concurrent writers, use existing
   serialization and reread/merge before publication. Atomic replacement alone
   cannot protect against a stale update losing another row.

If safe index publication is unavailable, retain the valid snapshot and report
its path with routing pending. The index is not a resource lock, and historical
ownership or cleanup statements are not current claim authority.

## Handoff notes

Authorized non-blocking requests may be appended to the currently referenced
handoff, including an archived starting snapshot. Follow project annotation
permissions. `Agent request` and `User request` identify provenance, not authority
to execute or change the receiving effort's plan.

Change only the dedicated `## Handoff notes` section; preserve the core snapshot,
routing index and existing notes. An explicit authorization to append the concrete
note is sufficient unless project policy requires additional confirmation.
Creating a note does not justify creating a snapshot.

Evaluate notes on pickup or requested review. Keep decisions and resulting work
in the receiving effort's owning record; file-based notes do not require direct
session messaging or acknowledgement.
