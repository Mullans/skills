# Explicit Draft Review

Read during an explicitly invoked retrospective when `pending-drafts` returns staged observations or an acceptance handoff needs recovery. Draft observations are not canonical instructions, verified outcomes, or new authority grants.

Run `recover-acceptance` to resume interrupted handoffs before preparing new acceptance operations. Recovery is explicit; hooks never perform it. It confirms an existing canonical receipt before completing the staged disposition, or applies an unchanged prepared manifest and then confirms its receipt. Inspect deferred errors rather than guessing missing evidence. A prepared but uncommitted operation can be abandoned with `cancel-acceptance --operation-id <id>` before revising or dismissing its draft; a committed operation must be recovered.

Read `pending-drafts --page 1` and subsequent pages. Pages include deferred items, counts, age, verification gaps, and revision hashes. Review visible-session findings and drafts through the normal decision, evidence, promotion, and reconciliation gates. If the draft is insufficient, preserve a verification gap and defer it. Pending backlog is never deleted automatically; capture warns once when it reaches 50 and resets below that threshold.

Use `review-draft --draft-id <id> --expected-sha256 <hash> --disposition deferred|dismissed --reason <reason>` for deferrals or dismissals. Reasons are `useful_new`, `useful_refinement`, `confirmation`, `low_impact`, `duplicate`, `already_enforced`, `unsupported`, and `verification_gap`. Accepted/dismissed records retain deduplication identity; materially new evidence or interpretation may reopen them through a guarded draft revision.

For an accepted finding, prepare an ordinary current-session canonical manifest for its proposed destination. Reconcile with existing guidance first: acceptance may create, refine, or confirm an existing lesson, without weakening its evidence gates. Run `accept-draft <manifest-file-or-> --draft-id <id> --expected-sha256 <hash> --reason useful_new|useful_refinement|confirmation`.

The handoff persists a bounded sanitized manifest and opaque operation ID in machine-local staging. The canonical changes and minimal receipt commit transactionally in the destination authority; only then is the draft marked accepted with resulting IDs. Receipts contain operation identity, manifest fingerprint, and canonical IDs, never draft text or staging paths. Identical replay returns the committed result; changed content under the same ID fails. Prepared draft revisions remain frozen until recovery or cancellation.

Handoffs accept canonical records and typed patches, not raw instruction file payloads. Engine-managed projections may follow from lesson delivery. Permission failures leave the review deferred without redirecting to another authority. Audit the canonical result separately after confirmation.
