# Resource checkout module

Read when concurrent sessions can interfere with shared mutable data, a device,
or an exclusive service. Use existing project coordination when present. Add this
module only for a concrete resource; ordinary workspace documentation needs no lock.

## What is packaged

- [Generic helper](../assets/resource-checkout/resource_lock.py): Python 3.10+
  standard library, no package dependencies.
- [Disposable tests](../assets/resource-checkout/test_resource_lock.py).
- [Procedure template](../assets/resource-checkout/procedure.md).

The helper separates a short-lived atomic directory guard from persistent claims.
It checks and acquires all requested resources in one guarded transaction, writes
the ledger through a flushed temporary file and atomic replacement, and identifies
each bundle with an owner plus random claim ID. Verification checks both identity
and requested scope. Release removes the entire bundle only after matching identity
and an existing nonempty final-state receipt. Claims never expire automatically.

Status also observes the guard: malformed/missing ledgers and abandoned guards
block coordination rather than reporting availability. The helper has no force,
steal, reset, or automatic migration operation.

## Select the authority before installing

1. Identify concrete resource IDs, physical scopes, and overlapping operations.
   Define incidental effects too: a launch can write data even when no edit was
   planned. For GPU use, identify the physical device; separate aliases for the
   same device defeat exclusion. Prefer conservative scopes over unmodeled overlap.
2. Choose ONE authority directory for all contenders, including separate checkouts.
   Each helper invocation must resolve that same path. A per-clone ledger or a
   Git/cloud-sync copy does not coordinate a shared device or dataset.
3. Use this file-based helper only where all contenders share a filesystem whose
   atomic mkdir/replace behavior is appropriate and tested. Multi-host services
   without such a common filesystem need a different authoritative backend.
4. State required final conditions per resource: restore and verify a baseline,
   or finish work and verify the GPU/process/service is idle. A receipt is evidence
   of the applicable final condition, not necessarily a rollback.

## Install into a new coordination setup

Copy the helper and its test alongside each other into a documented script
directory, such as `scripts/workspace/`. Run the test file with the project's
Python interpreter. All tests use temporary directories and synthetic resources;
never substitute live paths. Keep this helper outside distributable user tooling.

Adapt the procedure into `docs/resource-checkout.md`: fill resource scopes, authority
path, runnable interpreter commands, final-state requirements, and recovery contacts.
Add a conditional pointer from AGENTS and a navigation link. These local files must
be sufficient without the installed skill.

Create the chosen authority directory if needed, then initialize it ONCE:

```text
python scripts/workspace/resource_lock.py --state-dir <authority> init --resource "gpu=Physical GPU 0; exclusive experiments" --resource "dataset=The named mutable working dataset"
```

Use actual scopes, not this example. The authority directory must already exist.
The default state directory is the current directory; use an explicit shared path
when checkouts differ, or wrap the command in a short project entry point that
always selects it. Argument-free convenience must not silently select a different
authority.

Keep live state out of version-control synchronization: ignore `resource_lock.md`,
`.resource_lock.guard/`, and `.resource_lock-*.tmp` at the authority location
when it is inside a repository. Keep resource definitions and setup instructions
in tracked documentation; never ship an active claim or initialize over one.
Ensure routine cleanup tools exclude the guard and ledger. A restored checkout or
backup is not proof of current resource ownership.

Done: disposable tests pass, all contender paths point to one authority, the
resource scopes and final-state requirements are documented, and an initial
status check succeeds without acquiring live resources.

## Existing systems and recovery

Preserve an existing helper, schema, and active claims. This generic version uses
schema 2 and rejects the original game-specific version-1 ledger. The original's
legacy game-data coverage also includes saves; never drop that protection by
replacing its helper. Migration requires a separately approved plan and verified
quiescence, not ordinary setup or refresh.

For a crash or abandoned guard, stop and ask the user to inspect ownership, live
processes, and final state. Agents never clear another session's claim or remove
an abandoned guard. An old timestamp is not authority. A fresh session cannot
assume another session's identity by copying its label and claim ID.

## Limits

These are cooperative claims, not OS file locks or authentication. An actor with
filesystem access can bypass them or supply another owner's visible identity.
The helper cannot prove the calling agent is the recorded owner. Session policy
must enforce that identity, and all participating agents must honor the ledger.
Verification is a point-in-time check; hold the claim throughout the operation.

The helper checks receipt existence/nonemptiness, not its contents, resource hashes,
process termination, or actual restoration. The operator verifies those facts.
Atomic file replacement does not establish power-loss durability on every storage
system. Do not infer network-filesystem correctness from local tests.

Keep product safety checks (identity, restoration journals, ownership inside an
application) separate from experiment coordination. A standalone user tool should
not require the agent ledger to function.

## Provenance

Generalized from the source project's `scripts/workspace/resource_lock.py`
(SHA-256 `1907a76f45baebdccde0ecb755a9326e13bbac9e10107f8982fccca9a05195a4`)
and `tests/runtime/test_resource_lock.py`
(SHA-256 `b97949c3ed22c2780491e7b7f735eeb0a62de4190b452feb46899e20da63abf8`).
The originals remain unchanged. Generic resource registration, schema validation,
guarded status, explicit authority selection, and broader disposable tests are
adaptations; this is not a drop-in upgrade for the original live ledger.
