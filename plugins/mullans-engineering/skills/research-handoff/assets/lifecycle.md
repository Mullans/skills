# Cross-session handoffs

This document owns handoff eligibility, pickup, creation, publication and
archiving. A handoff preserves context needed by a later session; current work,
results and plans belong in the owning experiment or implementation record.

## Eligibility

Creating or modifying a continuation snapshot requires explicit user permission,
except when concrete unfinished work required to complete an incomplete
overarching goal must continue in a later session. Identify that goal, the
required unfinished work and why continuation is needed later.

Closing a task or session, waiting for user confirmation, continuing work in the
same session and picking up an existing handoff do not independently qualify.
Optional recommendations are not required unfinished work. Same-session planning
and waiting remain in the owning record; goal acceptance is separate from handoff
eligibility.

## Handoff notes exception

Non-blocking cross-effort requests may annotate the receiving effort's currently
referenced handoff, including an archived starting handoff. Agent requests may be
added autonomously; User requests require an explicit human request, a displayed
draft and confirmation to append. Change only the dedicated `## Handoff notes`
section, creating it on first use; preserve the core snapshot, routing index and
existing notes. Follow the research-handoff skill's note procedure for composition,
insertion and optional direct contact.

## Locations and index

`active/` holds pending continuation snapshots. `archive/YYYY-MM-DD/` holds
consumed or superseded snapshots; the directory date is the archiving date.
The root [next-handoff.md](../../next-handoff.md) routes to pending cross-session
continuations. Keep its rows concise; it is not a status log or historical ledger.
Project entry pages link to this index rather than competing continuation boards.

## Picking up work

Read the selected row, snapshot and relevant owning records. Reconcile discrepancies
encountered there with later evidence before acting; ordinary pickup does not
trigger a whole-project audit. Review appended notes on pickup or when explicitly
directed by the human; retain them intact and record decisions in the owning record.

Archive the consumed snapshot using the existing safe project helper, or move it
and repair its relative and inbound links. Preserve the original context and
unrelated pending continuations.

Keep current work in its owning record. Consuming a snapshot does not authorize
replacement. Remove its row once it no longer routes pending cross-session work;
if retaining it temporarily during pickup, keep the archived context link and
avoid turning the row into a session progress tracker. Do not archive a deferred
or unrelated continuation solely because it is old.

## Creating and publishing

Only after eligibility is established:

1. Write a unique `active/<topic>-<YYYYMMDD>[-sequence].md` using the
   [snapshot template](TEMPLATE.md). Record the incomplete overarching goal,
   required unfinished work, next action and supporting context. Accurately
   distinguish verified external state from unknown state; the relevant resource
   protocol and ledger retain authority over claims and restoration.
2. Save and validate the snapshot and its immediate links before changing its
   selected index row. If superseding an older snapshot, archive it while
   preserving links and evidence.
3. Reread the index, update only the selected routing row and preserve unrelated
   rows. Keep historical announcements and completed-work receipts in their
   owning records rather than the index.

For concurrent writers, use existing safe serialization and reread/merge within
its critical section. Atomic replacement alone does not prevent a stale read
from losing another row. If safe publication is unavailable, retain the valid
snapshot and report its path with routing pending. The index is not a lock.

Archive only continuation snapshots. Archiving does not authorize deletion or
relocation of investigation evidence, captures, baselines, source or other state.
