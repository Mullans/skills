# Shared resource checkout

<!-- SETUP: Adapt all resource names, authority paths, interpreter commands and
cleanup-owner links. Remove this note. This document must work independently
of the setup skill. Preserve an existing project protocol instead of replacing it. -->

## Authority and scope

| Resource ID | Exact physical/data scope | Operations requiring it |
| --- | --- | --- |
| gpu | Identify device | Exclusive experiments/jobs |
| dataset | Identify working dataset | Mutating or inconsistent concurrent access |

The authoritative state directory is `<authority>`. Every checkout and session
must select that same directory; independent ledger copies do not coordinate.
Use the project's `scripts/workspace/resource_lock.py` helper. Its Markdown ledger
contains a generated human view and authoritative JSON state. Only the helper
updates it. Resource scopes and aliases must represent actual overlap.

Read-only work and copies require no claim unless they themselves consume the
exclusive resource (for example, a GPU inference job). Claim every affected
resource together, including incidental writes or device use.

## Routine workflow

Preparation and safe cleanup follow the project's experiment protocol and
operation-specific helpers. Coordination grants no permission to mutate a system.

1. Claim all affected resources in one invocation:

   ```text
   python scripts/workspace/resource_lock.py --state-dir <authority> claim --resource gpu --resource dataset --owner "<unique-session>" --reason "<bounded operation>"
   ```

   Keep the returned claim ID in existing experiment state. Acquisition is atomic:
   any conflict acquires nothing and reports every requested resource's availability
   or conflicting owner and claim ID. Owner labels alone never establish ownership.
2. Perform authorized work and cleanup while holding the claims. Action helpers
   assert ownership internally; agents do not issue separate verification calls.
3. Release with the recorded identity unless cleanup already released successfully:

   ```text
   python scripts/workspace/resource_lock.py --state-dir <authority> release --owner "<unique-session>" --claim-id "<returned-ID>"
   ```

   Repeat `--claim-id` for multiple claims; optional repeated `--resource` selects
   resources to release. Otherwise all resources in the supplied claims are selected.
   Valid owned items are released even if other items conflict. Foreign claims are
   preserved. The command updates once and confirms removals under the same guard;
   results identify released, already absent, ownership mismatch or failure items.
   Nonzero exit includes partial failures; use the returned per-item results.
   Release neither reads evidence files nor certifies cleanup or restoration.

## Optional inspection and maintenance

`status` enumerates all registered resources and their current holders. Use it for
inspection or conflict recovery, not before claiming or after successful release.
It takes no resource, owner or claim selectors:

```text
python scripts/workspace/resource_lock.py --state-dir <authority> status
```

`init` is initial setup only; `refresh-display` regenerates the readable ledger
without changing claims. Neither is part of routine acquisition or release.

## Failures and continuity

Claims are persistent and have no expiry. The short-lived `.resource_lock.guard/`
serializes ledger access; a leftover guard blocks status and mutations. Do not
remove it automatically. Corrupt or missing ledgers are failures, not availability.
Initialization never resets an existing ledger. Coordinate recovery with the user.

Only the owning session may release its claim through the helper. Another
session's or abandoned claim stays held pending user recovery;
copying its label or ID does not make a new session its owner. Handoffs may record
identity and unresolved state for diagnosis, but never grant ownership.

The helper coordinates cooperating agents, not operating-system access. Keep
ledger/guard state out of Git or file-sync replication; all contenders need one
actual authority. Preserve local instructions and exclude these files from routine
cleanup. Changes to registered scopes or migration require coordinated quiescence
and a user-approved plan; there is no force/takeover command.
