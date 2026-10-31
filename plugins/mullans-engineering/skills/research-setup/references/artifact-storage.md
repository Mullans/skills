# Artifact workflow adoption

Use when establishing artifact storage or integrating an affected producer.

1. **Identify the authority.** Reuse the existing placement, registry, input
   resolution and cleanup interfaces. The installer preserves a detected existing
   system; use its `--artifact-mode existing` option for equivalents elsewhere.
2. **Establish the local owner.** For a new system, install the portable lifecycle
   guide and helper. Link the actual owner from documentation and agent routing;
   keep paths, retention values and project-specific policies with that owner.
3. **Integrate relevant writes.** Before an affected producer's first write,
   resolve its normal and alternate output destinations into owned storage.
   Include partial outputs and external working directories that this operation
   creates. Reuse shared inputs through the authority rather than copying them.
4. **Integrate closeout.** Reuse the existing action and batch helpers so evidence
   assessment and one closeout operation handle the scope. Keep live restoration,
   process control and resource release with the operations they protect.
5. **Check the changed integration.** Use temporary storage for relevant cases
   below. Report which producers are covered and any material gaps; do not claim
   repository-wide enforcement from a limited integration.

| Changed behavior | Cases to consider |
| --- | --- |
| Output ownership or routing | Normal/default destination, relevant overrides, rejection of unowned writes |
| Writer failure handling | Partial outputs and interrupted writes remain assessable |
| Input reuse | Correct shared input identity and consumer lifetime |
| Cleanup or retention | Assessed disposal, justified preservation and unresolved recovery |

Use the helper's existing APIs or CLI wrapper; implementation contracts live in
the [portable source](../assets/artifact-system/scripts/workspace/artifact_workspace.py)
and routine commands in the [lifecycle asset](../assets/artifact-system/docs/local-artifacts.md).
Install the helper into the project before integrating project imports.

Keep historical payload adoption and deletion outside ordinary setup. Do not
acquire live resources or start experiments to demonstrate storage behavior.
