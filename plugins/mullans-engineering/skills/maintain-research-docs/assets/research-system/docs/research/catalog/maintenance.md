# Research reference maintenance

The [wiki policy](../../wiki.md) owns placement and splitting; the
[templates](../reference-template.md) own unit shapes. This workflow concerns
organization, not scientific verification or new technical investigations.

## Audit and proposals

1. Run the audit recursively over `docs/research/` and registry paths. The tool
   determines eligibility and reports classification, measurements and errors;
   use its measured review set rather than inventing eligibility.
2. Review every flagged item under the wiki policy and reference template.
   Threshold eligibility requires review, not an automatic split. Record a
   disposition or explicit gap for every flagged item.
3. Inspect relevant supporting evidence through the catalog when citations,
   applicability or substantive support are affected. Organizational review does
   not certify scientific conclusions.
4. Prepare the concrete proposal bundle, exact patches/output identities and
   human-readable recommendations in a dated experiment.
5. Present all proposed decisions together. Wait for human approval before
   applying restructuring. Pending/rejected items remain unresolved.

Audit/proposal completion means every flagged item has a disposition or gap and
all required proposals are reviewable. A clean audit reports coverage and
diagnostics without resetting baselines.

```sh
python scripts/workspace/research_docs.py audit
python scripts/workspace/research_docs.py audit --format json
python scripts/workspace/research_docs.py propose --output experiments/YYYYMMDD-research-reference-review/proposal.json
```

Run from the workspace root. `propose --paths PATH PATH` selects a batch, including
below-threshold legacy pages. It creates pending proposals and refuses overwrite.
Complete exact patches/output hashes, recommendations, unit ownership, relocations,
factual changes and evidence issues before human review. Draft copies belong in
the investigation's catalog-excluded `drafts/` directory, not maintained subjects.
Catalog configuration `exclude_research_drafts: true` excludes these directories
under every investigation automatically, including future batches.

The [registry](maintenance.json) classifies every research Markdown page by stable
ID, role and rationale. Index/gateway/template/workflow exemptions require an
ownership judgment; mixed pages cannot hide reference content. `onboarded: false`
flags initial migration even below size thresholds. Page registry IDs are stable
names. The [reference template](../reference-template.md#page-shape) owns reference
unit headings, identifier grammar and counting boundaries.

## Measurements and thresholds

Defaults and per-page `overrides` use `word_threshold`, `unit_threshold` and
`change_percent`. This procedure owns measurement and baseline rules; the
[registry defaults and per-page overrides](maintenance.json) own configured
threshold values.

A page exceeding either size threshold without an accepted retain record needs
review. For previously retained pages, require both a current size-threshold
exceedance and sufficient change from the retained baseline. Compute change using
Git word diff: `100 * max(added_words, removed_words) / baseline_words`.
Size triggers use greater than; the change trigger uses greater than or equal to.
Do not reset the baseline on ordinary edits; small changes accumulate.
For an empty baseline, an oversized nonempty page is reviewable without dividing
by zero. These are review triggers, not mandatory split rules.

Git stores the exact retained comparison state; its identity must remain resolvable. Measurement
version changes invalidate incompatible comparisons rather than silently reusing
old metrics. Threshold changes recalculate eligibility against existing baselines.

The registry records page identity/path, applicable settings, exact retained Git
state, measurements, accepted rationale and measurement version. Proposed records
are separate from accepted baselines. The script derives measurements and records
new baselines after approved review; the reviewer supplies the decision/rationale.
Researchers need not interrupt experiments to assess page size.
Organizational measurement does not replace technical finding-validity checks.

Size counts visible words including tables and inline code, excluding fenced
code, comments, citation destinations and mechanical Standing/Review basis fields.
Comparison includes fenced technical code. Whitespace and heading/list/table/bold/
inline-code formatting are normalized; technical constants/punctuation remain.
Git word diff computes the change measure above from comparison projections.
Formatting/link-only repairs do not reopen size
review. Evidence validity remains separately checked by the research catalog.

Missing/empty baselines, invalid/duplicate IDs, unclassified pages, unresolved
citations and measurement failures are explicit diagnostics. Legacy unit counts
are preliminary until onboarding. Exit codes:0 complete/no reviews;1 complete/
reviews needed;2 incomplete/error. Citation lint checks links and unit-level
presence, not whether a source supports every claim; the reviewer checks each
sentence or wholly supported table group. Mixed-source rows need mapped citations.

## Approved batch sequence

Use current adopted wiki/template decisions when older wording differs. Report
the discrepancy without expanding maintenance into unrelated policy/tool repairs.
This document owns the maintenance sequence; setup installs its tools.
Concrete execution prefixes and prerequisite checks belong in the project toolchain
guide. Keep the direct Python interfaces below unless an explicit project decision
changes them.

1. Identify approved proposal items and execution authorization. Validate exact
   source and patch identities immediately before applying; stale sources or
   changed proposed outputs require reconciliation and renewed human review.
2. Apply only approved bytes, preserve unit IDs/evidence/applicability, repair
   inbound links and remove obsolete navigation under the wiki policy.
3. Run catalog, citation/link and staged-content checks. Resolve evidence issues;
   technical validity is separate from organizational approval.
4. Commit approved documents using the selective isolated-index helper. Preserve
   unrelated index entries; hold overlapping staged changes that cannot be safely
   separated. Wait for the document commit to complete.
5. Finalize all approved items together in one call. Let the tool discover their
   document revisions; do not supply revisions individually or finalize one item
   at a time. Wait for finalization to complete.
6. Commit finalized registry metadata separately, then record decisions, checks,
   both commits and unresolved items in the owning experiment.

The batch is complete only after every approved item passes validation, is
document-committed and finalized, and the registry commit and closeout are recorded.
Otherwise report the exact unfinished stage and blocker.

### Proposal and source validation

Each item carries source SHA256 values, pending/approved/rejected status,
retain/split/onboard action, rationale, exact output identities/hashes, patches,
relocations and evidence issues. Set `citation_support` to `accepted` only after
review; set `technical_evidence` to `unchanged` or `reviewed` honestly. Retention
certifies organization, not truth. Do not replace support fingerprints merely
to clear warnings. Pending/rejected items never reset accepted baselines.

After approval, the operator calls `validate_sources(root, bundle)` immediately
before applying patches. It rejects changed source/patch hashes. The validator checks only approved
items. To validate a pending proposal for review, deep-copy its bundle and mark
only intended validation items approved in memory; leave saved approvals pending.
Report which items were actually checked. This grants no application authority. Apply only exact
approved results, repair inbound links/catalog routes, and run catalog/link checks.
The explicit operator API `commit_batch(root, proposal_path, message)` uses an
isolated index, checks exact approved bytes/whitespace, preserves unrelated staged
entries and blocks overlapping staged changes. Audit/propose/finalize never call
it implicitly. Normal staging is also allowed when the index is batch-only.
Commits require task authorization; no unrelated work or history is rewritten.

## Batch finalization

After committing approved documents, invoke once per bundle:

```sh
python scripts/workspace/research_docs.py finalize --proposal experiments/YYYYMMDD-research-reference-review/proposal.json --dry-run
python scripts/workspace/research_docs.py finalize --proposal experiments/YYYYMMDD-research-reference-review/proposal.json
```

Finalization discovers latest document commits reachable from captured HEAD.
Approved bytes must match HEAD, the discovered
document commit, worktree and regular index. All approved items are checked before
any registry write; one failed item blocks the whole batch. `retire` lists replaced
page IDs. Renames/splits use explicit destination paths. Pending/rejected items
remain unresolved. Repeating successful finalization is idempotent.

Writes acquire ignored `local/research-doc-maintenance/finalize.lock`, recheck
registry/HEAD/documents/index and atomically replace the registry. Existing locks
are never expired or taken over; investigate their owner before authorized manual recovery.
Dry runs write nothing and acquire no lock. Missing Git objects are errors, not
permission to substitute another version. Commit finalized metadata separately
as one authorized registry commit. Keep review history and unresolved items in their owning investigations. This documentation workflow grants no authorization for live experiments.

## Failed and incomplete operations

Treat audit exit 1 as a successful measured review requirement; exit 2 is
incomplete/error and cannot establish no work. Missing baselines, unavailable Git
objects, changed approvals, unresolved citations, measurement failures and held
finalization locks stay visible. Correct the specific blocker using the tools'
safeguards; never substitute another baseline or reset a pending review.
Dependent operations run sequentially. A failed finalization leaves the document
commit recorded but the batch unfinished; reconcile before retrying. A successful
repeat is idempotent. A clean audit reports its coverage and diagnostics without
resetting accepted baselines. Keep pending/rejected decisions in the proposal.
