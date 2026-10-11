---
name: maintain-research-docs
description: Audit research-reference organization, prepare maintenance proposals, or apply an approved batch using the research pipeline's wiki, catalog and batch-review system. Use for reference maintenance rather than current-session promotion.
---

# Maintain research docs

Own the reusable wiki policy, reference-unit conventions, catalog review and
numbered maintenance procedure for the four-skill research pipeline. Standard
project paths are established by `research-setup`. `research-promotion` owns
current-session milestone promotion; `research-handoff` owns continuation.

## Choose the stage

Begin a new maintenance review with the existing maintenance audit. Prepare
proposals for flagged items without approval; when the concrete batch already
has human approval and execution authorization, validate and apply it without
requesting approval again. Skill invocation does not approve restructuring or
authorize a commit. Maintenance concerns organization; scientific verification,
capability audits and new experiments remain separate tasks.

## Load the owning guidance

The following standard paths are part of this pipeline, not arbitrary per-project
choices. Read project copies for configured values and adopted decisions. The
linked bundled assets supply the reusable policy and defaults that setup installs.
When adopting an established equivalent layout, record its owner mapping in
`docs/README.md` and use that mapping consistently. The packaged maintenance
tool expects `docs/research/catalog/maintenance.json`; register nonstandard
reference paths there. Catalog roots and subjects are configurable in its JSON
configuration. A prose mapping alone does not reconfigure tool paths; verify
compatibility and propose any required migration before using an equivalent.

| Project owner / bundled default | Load condition |
| --- | --- |
| `docs/research/catalog/maintenance.md` â€” [maintenance procedure](assets/research-system/docs/research/catalog/maintenance.md) | Audit/proposal commands, source checks, selective commits, finalization and errors |
| `docs/wiki.md` â€” [wiki policy](assets/research-system/docs/wiki.md) | Placement, ownership, redundancy, consolidation or splitting |
| `docs/research/reference-template.md` â€” [reference template](assets/research-system/docs/research/reference-template.md) | Finding, contract or negative-result units |
| `docs/research/catalog/README.md` â€” [catalog guidance](assets/research-system/docs/research/catalog/README.md) | Prior evidence, applicability and changed-support review |

Use current adopted wiki/template decisions when older wording differs. Report
the discrepancy; keep unrelated policy/tool repairs outside the maintenance batch.
Setup installs the packaged tools under `scripts/workspace/`; use their interfaces
for discovery, measurements, source validation, selective commits and revision
discovery. Missing infrastructure requires the bounded setup installation/adoption
step, not a replacement ad hoc procedure. Run commands with the project's recorded
interpreter/execution prefix and retain their arguments and error semantics.

## Audit and propose

1. Run the maintenance audit recursively across `docs/research/` and registered
   paths. The audit script determines the review set; do not add documents to
   that set manually. Report classification, measurement and coverage errors
   rather than interpreting them as no work.
2. Review every flagged item with the owning policy, template and relevant
   evidence. Threshold eligibility does not mandate splitting. Structural checks
   and organizational approval do not certify technical claims; inspect affected
   support before changing substantive fingerprints.
3. Assess splitting, consolidation, placement and changed support under the
   owning policies; record the recommendation and its evidence.
4. Use the proposal tooling to prepare exact patches, source/output hashes,
   recommendations, evidence issues and a readable summary in the owning dated
   experiment. Keep draft copies excluded from catalog retrieval. Collect technical
   conflicts for one user decision round; preserve original evidence and IDs.
5. Present the concrete batch and wait for human confirmation before applying
   changes. Pending/rejected items remain unresolved and do not reset baselines.

Complete when every flagged item has a disposition or explicit gap, needed
proposals are concrete and pending decisions are presented. A clean audit reports
its scope without resetting accepted baselines.

## Apply an approved batch

1. Identify the approved items and existing execution authorization. Validate
   source/patch identities immediately before application. Changed sources or
   results require reconciliation and renewed review of the affected approval.
2. Apply only approved results under the wiki/template policy. Preserve unrelated
   work, finding identities, original evidence and applicability. Repair inbound
   navigation directly and remove obsolete routes under that policy.
3. Run catalog, citation/link and staged-content checks. Resolve support issues
   before presenting affected claims as verified reference knowledge; structural
   or fingerprint success does not establish an accurate paraphrase.
4. Commit the approved document batch through the selective-commit helper. Preserve
   unrelated index entries and hold overlapping staged changes that cannot safely
   be separated. The helper commits exact approved output bytes.
5. After the document commit, finalize the batch together. Let the helper discover
   document revisions; do not supply individual revisions or finalize one document
   at a time. Wait for each dependent operation before starting the next.
6. Commit finalized registry metadata separately. Record decisions, checks,
   document/registry revisions and unresolved items alongside the experiment's
   proposal. History stays outside reference pages.

Complete when approved items are validated, document-committed and successfully
finalized, followed by the registry commit and closeout record. Otherwise report
the exact unfinished stage. Held locks, missing baselines, stale approvals and
conflicts stay visible under the packaged tools' safeguards.
