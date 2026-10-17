# Artifact workflow adoption

Use this branch when installing or reconciling local storage management.

1. Identify the existing registry, placement guide, lifecycle policy, reusable
   input resolver and cleanup command. Preserve equivalent project interfaces.
   The installer leaves an existing artifact system for adaptation rather than
   introducing a second authority.
2. For a new system, install the bundled portable helper and lifecycle owner.
   Reconcile `docs/README.md` placement and agent/protocol pointers. Keep project
   policies such as baseline retention and tool cache paths in their topic owners.
3. Integrate maintained producers before their first write. Resolve parser
   defaults, equals-form and alternate output flags; provide ownership through
   an experiment flag, workflow context or registered destination. Route external
   tool working directories and partial outputs into experiment storage. Keep
   callable APIs and standalone user tools independent of agent resource checkout.
4. Use the helper's `Store.run` or CLI wrapper for custom/standalone generation.
   Declare transient inputs and resolve shared references rather than copying.
   Integrate closeout in the owning experiment workflow; agents assess evidence
   once and run one finish command, without per-file claim-release bookkeeping.
   Add deterministic recipes only for worthwhile expensive work; freshly packed
   candidates still require independent verification.
5. Adapt existing snapshot helpers to register recovery before mutation and
   attach their verified recovery proofs afterward. Real restoration checks,
   process/writer closure and shared-resource release stay operation-specific.
   The portable helper does not implement platform process control, live recovery
   or a universal backup policy.
6. Run disposable checks for rejected writes, defaults/direct entry points,
   partial failures, independent verification, stale reuse, consumer closeout,
   interrupted writers, preservation and explicit cleanup. Report every producer
   that still writes elsewhere as an integration gap, not a supported guarantee.

The source asset lives under `assets/artifact-system/`; install it into the
project before adapting imports or wrappers. The installed lifecycle document
owns routine commands and retention rules. Keep tests outside the distributed
skill and use temporary fixtures. Setup never scans, adopts or deletes historical
payloads, acquires live resources, or starts experiments to demonstrate storage.
