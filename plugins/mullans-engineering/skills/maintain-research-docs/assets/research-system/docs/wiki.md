# Research wiki policy

`research-setup` installs this reusable research structure. The four research
skills own its workflow; project configuration supplies concrete commands,
threshold overrides, tool contracts and subject-specific decisions. Keep adopted
project policy here when it differs from the supplied defaults, with its rationale.

[Research index](research/README.md) routes maintained knowledge;
[next-handoff.md](../next-handoff.md) routes active work. The evidence catalog
provides retrieval, not a second authoritative copy of the research.

## Placement rules

- Subject pages own supported reusable facts/contracts and links to original evidence.
- Experiments own dated observations, failed attempts and investigation history.
- Experiments own trial procedures and execution state; `docs/handoffs/` owns
  session stopping points and resume instructions. Reusable operating procedures
  stay in their designated workflow/tool guides.
- `docs/references/` owns external reports and outbound research briefs.
- Dated reviews and superseded design plans belong with their owning investigations.
- A topic index routes readers; it does not repeat every finding or keep another queue.

## Reference purpose

Subject pages are quickly discoverable factual references. Include verified
statements and the conditions and limitations necessary to interpret them;
provide direct links for investigation details, justification and related topics.
Hypotheses remain in investigations or handoffs until verified. A related task
should not encounter an unconfirmed explanation presented alongside established
knowledge. Retain confirmed technical reference details, including bindings,
layouts, IDs and scoped negative results. Move experimental procedure, status
reports and details relevant only to continuing a particular experiment into
its investigation. Source links supply optional background and justification;
ordinary reference entries should not require reading an entire linked document.

A topic is a coherent family of reference questions about an object, mechanism
or contract. Split when each child answers a distinct question, has established
knowledge worth maintaining independently, and most entries have one owner.

Use [the reference template](research/reference-template.md) for approximate
finding, technical-contract and negative-result units. Keep existing finding IDs
and review fields intact. Count each explicitly identified unit once; individual
table rows, scope, sources and navigation are not additional units.

## Scripted organizational review

Global defaults and optional per-page overrides live in a maintenance registry:

| Setting | Initial default |
| --- | ---: |
| Page word threshold | 2,000 |
| Reference-unit threshold | 12 |
| Change percentage after retention | 20% |

A page exceeding either size threshold without an accepted retain record needs
review. For previously retained pages, require both a current size-threshold
exceedance and sufficient change from the retained baseline. Compute change using
Git word diff: `100 * max(added_words, removed_words) / baseline_words`.
Size triggers use greater than; the change trigger uses greater than or equal to.
Do not reset the baseline on ordinary edits; small changes accumulate.
For an empty baseline, an oversized nonempty page is reviewable without dividing
by zero. These are review triggers, not mandatory split rules.

The script counts visible reference words, including tables, excluding code
blocks and mechanical review metadata. Change comparisons include authored
technical content, including changed constants and code examples, while excluding
formatting-only, mechanical-metadata and source-link-only repairs. Git stores the
exact retained comparison state; its identity must remain resolvable. Measurement
version changes invalidate incompatible comparisons rather than silently reusing
old metrics. Threshold changes recalculate eligibility against existing baselines.

The registry records page identity/path, applicable settings, exact retained Git
state, measurements, accepted rationale and measurement version. Proposed records
are separate from accepted baselines. The script derives measurements and records
new baselines after approved review; the reviewer supplies the decision/rationale.
Researchers need not interrupt experiments to assess page size. Out-of-scope
additions require an ownership judgment at promotion, independent of size review.
Organizational measurement does not replace technical finding-validity checks.

## Citation and review workflow

Every factual statement has a source citation. A citation may follow a group or
table when it supports every fact in that group; mixed-source facts need their
own citations. Link supporting sections directly. Confirmed bindings, layouts,
identifiers and contracts remain in reference pages; experiment procedure and
status remain in investigations.

Include scoped negative results when no relevant positive result supersedes
them. When a later verified positive construction answers the same reference
question within the relevant scope, replace the negative entry with the positive
reference and cite the supporting earlier investigation where appropriate.
Preserve the original negative observation in its experiment. Do not imply an
earlier failure establishes a prerequisite or cause that was never isolated.

The maintenance process has two passes. First, run the eligibility script and
review flagged documents, producing proposed retain records or split plans and
a human-readable summary. The human approves or rejects each proposal. Second,
apply only approved restructuring and finalize approved registry baselines with
the script. A proposed retain record does not reset review eligibility. Rejected
or pending proposals do not silently become accepted decisions. Approval applies
to the reviewed source version; changed source requires reconciliation before
applying the proposal. The script reports missing baselines, unmarked units
and measurement errors explicitly rather than interpreting them as no review
needed. Use [the maintenance guide](research/catalog/maintenance.md) for the
implemented audit/propose/finalize commands and registry. Legacy subject pages
remain explicitly flagged until their approved reference-unit migration.
Approved document changes are staged and committed as a batch before finalization.
One finalization call discovers all affected document commits and records accepted
baselines; the resulting registry updates are committed separately.

For a substantive result, follow [research promotion](#research-promotion).
Cite the owning reference unit from other topics. Put continuation state in a
handoff and update `next-handoff.md` only when actual active work changes.

Each wiki subject should have: a short scope, addressable verified findings,
factual applicability limits, links to contract/usage pages, and evidence/history pointers. Remove
duplicated introductory summaries when they simply restate a finding below.
Do not add another global status page, duplicate catalog, or manually maintained
finding database. Split a page when distinct decisions cannot be reached through
its headings; move complete blocks and repair links instead of duplicating them.

Further semantic splits follow the
scripted maintenance and human-approved batch process above. Normal subject work
promotes verified units to their owning references; organizational audits decide
whether accumulated growth justifies splitting. This policy authorizes no new
research or live experiments.

Reorganization updates inbound links directly and removes obsolete pages. Do not retain compatibility gateways, aliases or old anchors. Verified references omit redundant Standing fields; source-review warnings and explicit scope/limits remain.


## Research promotion

Record new findings, reasoning, trial procedures and history in the owning
experiment first. At a milestone where supported reusable knowledge informs
subsequent work, use `research-promotion` to codify this session's findings.
Assume older experiments already reviewed; inspect prior sources only for a
specific support/reconciliation need unless a broader review is requested.

Use the [reference template](research/reference-template.md) and
[catalog conventions](research/catalog/README.md#finding-convention). Review each
precise claim against decisive evidence in a separate semantic pass before
publishing it. Preserve applicability, confidence where required, factual limits,
IDs and precise support links. Routine promotion may be reviewed by the session
agent; sufficiently complex promotion requires an independent reviewer. Keep
unreviewed drafts in the experiment until that review is available.

Clear supersession within the same question and scope may proceed routinely;
retain the original observation in its experiment. Hold contradictions and
dependent claims, add a precise source-linked revalidation warning to the affected
existing claim, and present all conflicts together for the user's resolution.
Independent uncontested findings may proceed while those decisions are pending.

Keep historical logging, procedures, temporary state and unresolved interpretations
outside reference pages. Procedural guides, including catalog/readiness/recovery
guidance, retain their operational role even when located under `docs/research/`.
Promotion may yield no qualifying reference changes. Handoff reconciliation
preserves outcomes independently of promotion. The four research skills are installed together: `research-setup` establishes
this structure, `research-promotion` elevates supported knowledge,
`maintain-research-docs` maintains references, and `research-handoff` preserves
session continuity.

Routine promotion uses established link/catalog checks and leaves organizational
baselines intact. Splitting, consolidation and organizational audits use
`maintain-research-docs` and the [maintenance procedure](research/catalog/maintenance.md).
Policy changes and substantial restructuring require a user decision unless
already authorized. Record promotion history and review outcomes in experiments.
