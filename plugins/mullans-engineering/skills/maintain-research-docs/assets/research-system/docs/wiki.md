# Research reference policy

This document owns the content, organization and promotion of maintained research
references. The [research index](research/README.md) owns subject navigation.
Use the [reference template](research/reference-template.md) for unit shapes,
the [catalog](research/catalog/README.md) for retrieval and support checks, and
the [maintenance procedure](research/catalog/maintenance.md) for organizational
audits, approvals and baseline finalization. Keep adopted project policy here
when it differs from supplied defaults, with its rationale.

## Placement rules

- Subject pages own supported reusable facts/contracts and links to original evidence.
- Experiments own dated observations, failed attempts and investigation history.
- Experiments own trial procedures and execution state. Reusable operating
  procedures stay in their designated workflow/tool guides.
- `docs/references/` owns external reports and outbound research briefs.
- Dated reviews and superseded design plans belong with their owning investigations.
- A topic index routes readers; it does not repeat every finding or keep another queue.

## Reference purpose

Subject pages are quickly discoverable factual references. Include verified
statements and the conditions and limitations necessary to interpret them;
provide direct links for investigation details, justification and related topics.
Hypotheses remain in investigations until verified. A related task
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
and review fields intact.

## Scripted organizational review

Use the [maintenance procedure](research/catalog/maintenance.md) for review
thresholds, measurements, proposal approval and committed-baseline finalization.
Size triggers prompt an ownership judgment; they do not mandate splitting.
Out-of-scope additions require an ownership judgment at promotion independently
of size review.
Organizational review does not certify technical claims.

## Citation and review workflow

Every factual statement has a source citation. A citation may follow a group or
table when it supports every fact in that group; mixed-source facts need their
own citations. Link supporting sections directly and place citations beside the supported claims;
a page-wide bibliography alone does not map support. Confirmed bindings, layouts,
identifiers and contracts remain in reference pages; experiment procedure and
status remain in investigations.

A negative result must supply reusable technical knowledge rather than merely
report an unsuccessful session. Include scoped negative results when no relevant positive result supersedes
them. When a later verified positive construction answers the same reference
question within the relevant scope, replace the negative entry with the positive
reference and cite the supporting earlier investigation where appropriate.
Preserve the original negative observation in its experiment. Do not imply an
earlier failure establishes a prerequisite or cause that was never isolated.

For a substantive result, follow [research promotion](#research-promotion).
Cite the owning reference unit from other topics.

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
[catalog conventions](research/catalog/README.md#structured-findings-and-support-warnings). Review each
precise claim against decisive evidence in a separate semantic pass before
publishing it. Preserve applicability, confidence where required, factual limits,
IDs and precise support links. The session agent may perform the review. Require
independent review for a specific consequential claim whose evidence or reasoning
the session agent cannot adequately verify. Hold only the affected claims when
that review is unavailable; complexity alone does not require another reviewer.

Clear supersession within the same question and scope may proceed routinely;
retain the original observation in its experiment. Hold contradictions and
dependent claims, add a precise source-linked revalidation warning to the affected
existing claim, and present all conflicts together for the user's resolution.
Independent uncontested findings may proceed while those decisions are pending.

Keep historical logging, procedures, temporary state and unresolved interpretations
outside reference pages. Procedural guides, including catalog/readiness/recovery
guidance, retain their operational role even when located under `docs/research/`.
Promotion may yield no qualifying reference changes. Investigation closeout
preserves outcomes independently of promotion.

Select promotion checks for changed links, metadata or support under the
[experiment protocol](research/experiment-protocol.md#preparation-and-checks);
leave organizational baselines intact. Splitting, consolidation and organizational audits use
`maintain-research-docs` and the [maintenance procedure](research/catalog/maintenance.md).
Policy changes and substantial restructuring require a user decision unless
already authorized. Record promotion history and review outcomes in experiments.
