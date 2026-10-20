# Explicit Draft Review

Use during an explicit retrospective when `pending-drafts` finds observations or interrupted acceptance. Apply [decision-policy.md](decision-policy.md); drafts are not canonical instructions or verified outcomes.

1. Run `recover-acceptance` before preparing new acceptance operations. Resolve reported errors. Cancel a prepared but uncommitted operation with `cancel-acceptance --operation-id <id>` before revising/dismissing its frozen draft. A committed operation must be recovered, not cancelled. Hooks never recover acceptance.
2. Discover with `pending-drafts --summary --page 1` and relevant subsequent pages; report uncovered backlog. Use `read-draft <id>` for a selected draft's full record and review hash. Inspect observations and verification gaps against visible evidence and existing guidance. Resolve staging issues; defer insufficient evidence without filling gaps from a plan or memory.
3. For deferral/dismissal use `review-draft --draft-id <id> --expected-sha256 <hash> --disposition deferred|dismissed --reason <reason>`. Command help lists reasons. Preserve the actual verification gap.
4. For acceptance, prepare a current-session canonical manifest through [patch-authoring.md](patch-authoring.md). It may create, refine, or confirm reconciled guidance. Run `accept-draft <manifest-file-or-> --draft-id <id> --expected-sha256 <hash> --reason useful_new|useful_refinement|confirmation`.
5. Confirm canonical acceptance before reporting the draft accepted; then audit separately. Identical replay returns the committed result; changed content under the same operation ID fails. Permission failures leave review deferred; retain authority rather than redirecting writes.

Handoffs accept canonical records/typed patches, not raw instruction files. Projections are engine-managed. Prepared drafts remain frozen until recovery or cancellation. Accepted/dismissed observations retain deduplication identity; materially new evidence/interpretation may reopen them through a guarded revision. Pending backlog is not automatically deleted.
