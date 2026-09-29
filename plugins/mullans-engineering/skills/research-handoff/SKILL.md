---
name: research-handoff
description: Create or update a continuation handoff, or capture a quick checkpoint, when the user asks to preserve research or implementation work for another session.
---

# Research handoff

Preserve the selected work for another session in response to the user's request.
This skill works independently in an ordinary project or scratch folder.

## 1. Find or create the local structure

Read applicable instructions. Use session context and targeted inspection to
identify the workstream and stopping point; clarify scope only if ambiguous.
Find its existing index, snapshot template, and lifecycle procedure. Preserve
established paths, active/archive helpers, and unrelated work.

When structure is missing or needs adaptation, read
[handoff formats](references/formats.md) and create only the needed files. Research
setup, Git, a taxonomy, and a resource ledger are not prerequisites.

Done: the workstream, normal-handoff or quick-checkpoint mode, snapshot destination,
and index to update are identified; missing structure has a defined minimal default.

## 2. Reconcile outcomes

For a normal handoff, update the records that own relevant results and checks.
Qualify useful findings with scope, evidence, uncertainty, and contrary results,
using local conventions when available. If there are no owning records, keep
needed context in the snapshot; create a separate note only for a reusable finding.

Preserve an error explanation when it prevents recurrence or aids future diagnosis:
symptoms, cause, useful diagnostic method, fix, and verification. Link existing
explanations. Log retention and cleanup are separate decisions; handoff creation
does not authorize deletion.

For a quick checkpoint, capture the stopping point, immediate risks, active
artifacts, and next action; name reconciliation still owed.

Done for a normal handoff: relevant outcomes are reconciled into their owning
records or the snapshot; any unavoidable gap is reported with its cause and next
action. Do not silently downgrade a normal handoff to a quick checkpoint.
Done for a quick checkpoint: the next action or blocking prerequisite is clear,
and unfinished reconciliation is explicit.

## 3. Record relevant state

Check relevant repository changes and immediate input availability. Record
applicable completed checks and the conditions that would require repeating them.
Capture revision identity and relevant uncommitted work where useful. Preserve
work without staging, committing, or publishing unless separately requested.

For external state, use read-only evidence or already-authorized restoration
procedures. State uncertainty and recovery prerequisites rather than launching
live tests merely to complete a handoff.

If shared-resource coordination applies, follow the project's ledger and helper.
Record its authority location, affected resources, recorded owner/claim ID, and any
final-state receipt needed for continuation; these references do not transfer
ownership. Verify ownership before live operations; release only this session's
claim after required final-state verification and within authorized scope. Never
directly edit a ledger or take over another owner's or abandoned claim; ask the user to
resolve it. Handoff status and elapsed time do not grant ownership. If no protocol
exists, record coordination needed before future live work without inventing claims.

Done: every immediate prerequisite has a location and known availability or an
explicit gap; reported external state and verification distinguish facts from
unknowns.

## 4. Write and route the snapshot

Use the local template, or adapt [the snapshot template](assets/handoff.md).
Provide a short stopping-point summary and precise links to existing detail.
Include a command when finding it would otherwise be costly. Rebase links for
the snapshot's actual location.

Save and validate the snapshot before updating its index pointer. Reread the index
immediately before changing only the selected row; preserve other rows and history.
When concurrent index writers are possible, follow
[publication coordination](references/formats.md#publication-coordination).
Use the local lifecycle, or [handoff formats](references/formats.md) when creating
or adapting one.

Done: the snapshot identifies the next action, its prerequisites and completion
criterion; the selected index row points to it and agrees about current work,
or a publication blocker is explicitly reported with the saved snapshot path.

## 5. Verify and return

Check changed links and immediate artifact references, using an existing safe
checker when available. Report missing prerequisites and deferred reconciliation.
Return the handoff link, next action, and material blockers concisely.

Done: a new session can reach the next action and needed context without the prior
conversation. Ordinary resume reads that context and reconciles discrepancies
encountered there; it does not trigger a whole-project drift audit.
