# Shared resource checkout

<!-- SETUP: Adapt all resource names, authority paths, interpreter commands and
final-state requirements. Remove this note. This document must work independently
of the setup skill. Preserve an existing project protocol instead of replacing it. -->

## Authority and scope

| Resource ID | Exact physical/data scope | Operations requiring it | Required final condition |
| --- | --- | --- | --- |
| gpu | Identify device | Exclusive experiments/jobs | Owned jobs stopped; device available |
| dataset | Identify working dataset | Mutating or inconsistent concurrent access | Agreed baseline or committed final state verified |

The authoritative state directory is `<authority>`. Every checkout and session
must select that same directory; independent ledger copies do not coordinate.
Use the project's `scripts/workspace/resource_lock.py` helper. Its Markdown ledger
contains a generated human view and authoritative JSON state. Only the helper
updates it. Resource scopes and aliases must represent actual overlap.

Read-only work and copies require no claim unless they themselves consume the
exclusive resource (for example, a GPU inference job). Claim every affected
resource together, including incidental writes or device use.

## Operation sequence

1. Establish task authorization, targets, prerequisites, backups/rollback when
   applicable, stop conditions, and the intended final state before live work.
   Coordination alone grants no permission to mutate a system.
2. Check status, then claim all required resources in one invocation:

   ```text
   python scripts/workspace/resource_lock.py --state-dir <authority> status
   python scripts/workspace/resource_lock.py --state-dir <authority> claim --resource gpu --resource dataset --owner "<unique-session>" --reason "<bounded operation>"
   ```

   Record the returned claim ID in the task checkpoint. A conflicting claim blocks
   the whole bundle; no resource is partially acquired. Even the same owner label
   cannot claim an already held resource again.
3. Immediately before each relevant live operation, verify the complete scope:

   ```text
   python scripts/workspace/resource_lock.py --state-dir <authority> verify --resource gpu --resource dataset --owner "<unique-session>" --claim-id "<returned-ID>"
   ```

   Failure means stop. Keep ownership through work, cleanup, rollback and final
   verification. Verify again before rollback operations.
4. Verify actual final conditions and write a small receipt naming the resources,
   owner/claim ID, checks performed, outcomes, and relevant evidence. A GPU receipt
   may attest that owned jobs ended; a data receipt may cite restoration hashes.
5. Release the full bundle with the same identity:

   ```text
   python scripts/workspace/resource_lock.py --state-dir <authority> release --owner "<unique-session>" --claim-id "<returned-ID>" --evidence "<receipt-path>"
   ```

   Receipt paths are relative to the current directory unless absolute. The helper
   checks the file exists and is nonempty; the operator validates its contents and
   the actual state. Confirm the released state with status.

## Failures and continuity

Claims are persistent and have no expiry. The short-lived `.resource_lock.guard/`
serializes ledger access; a leftover guard blocks status and mutations. Do not
remove it automatically. Corrupt or missing ledgers are failures, not availability.
Initialization never resets an existing ledger. Coordinate recovery with the user.

Only the owning session may release its claim through the helper after final
verification. Another session's or abandoned claim stays held pending user recovery;
copying its label or ID does not make a new session its owner. Handoffs may record
identity and unresolved state for diagnosis, but never grant ownership.

The helper coordinates cooperating agents, not operating-system access. Keep
ledger/guard state out of Git or file-sync replication; all contenders need one
actual authority. Preserve local instructions and exclude these files from routine
cleanup. Changes to registered scopes or migration require coordinated quiescence
and a user-approved plan; there is no force/takeover command.
