---
name: maintain-research-docs
description: Review research-reference organization, prepare concrete maintenance proposals, or apply an approved batch. Use for organizational maintenance rather than current-session finding promotion or capability audits.
---

# Maintain research docs

Own the reusable organizational-review procedure. Use the project's maintenance
guide for local commands and configuration. Direct corrections and routine
promotion do not require this batch process or a reset of accepted baselines.

## Select scope and guidance

Identify the requested review, selected pages and existing approval. A scoped
review need not resolve unrelated legacy pages; a full audit must account for its
declared coverage. Continue an already approved batch from its unfinished stage.

Prefer adopted project owners over packaged defaults. Load only what the current
decision needs:

| Decision | Project owner / bundled default |
| --- | --- |
| Local commands, settings and outcomes | [Maintenance guide](assets/research-system/docs/research/catalog/maintenance.md), normally `docs/research/catalog/maintenance.md` |
| Placement, splitting or substantive reference changes | [Reference policy](assets/research-system/docs/wiki.md), normally `docs/wiki.md` |
| Reference unit fields | [Template](assets/research-system/docs/research/reference-template.md) |
| Prior knowledge or a support concern | [Catalog guide](assets/research-system/docs/research/catalog/README.md) |
| Experiment planning or evidence interpretation | [Experiment protocol](assets/research-system/docs/research/experiment-protocol.md) |
| Proposal/API details or interrupted maintenance | [Maintenance tooling](references/maintenance-tooling.md) |

Resolve equivalent owners through project navigation. The maintenance tool reads
its registry at `docs/research/catalog/maintenance.json`; catalog paths are
configured in its JSON. A prose mapping does not reconfigure a tool. Use installed
interfaces and the project's execution prefix; install missing infrastructure
only when the selected operation needs it.

## Audit and propose

1. **Identify the review set.** For an organizational audit, use the existing
   audit tool to find measured flags and diagnostics. For a directed review,
   select the requested pages. Size flags invite judgment, not automatic splits.
2. **Assess ownership and retrieval.** Follow project policy. Preserve complete
   reference units and their IDs, substantive review dates and support
   fingerprints during mechanical moves. Review changed claims, contradictions
   or specific support concerns; do not re-prove unchanged findings.
3. **Prepare concrete changes.** Use the proposal tool for a tracked batch.
   Supply destinations, exact proposed outputs, rationale, affected navigation
   and unresolved issues. Keep review drafts in the owning investigation's
   `drafts/` directory, outside maintained subject content.
4. **Present decisions.** Make the selected changes reviewable and identify any
   material exclusions or gaps. Apply required approval rules; do not ask again
   for an already approved result within existing authorization. Pending or
   rejected items do not change accepted baselines.

## Apply an approved batch

1. **Validate immediately before application.** Use the source/patch validator
   described in the tooling reference. Changed reviewed inputs require
   reconciliation of the affected approval.
2. **Apply the approved result.** Preserve unrelated work. Update active incoming
   links directly and remove obsolete pages without compatibility gateways.
   Preserve dated requests and investigation history.
3. **Check affected changes.** Select link, metadata or support checks for the
   actual edits. Mechanical relocation does not require another scientific
   review or a new experiment.
4. **Commit documents when authorized.** Use scoped staging or the selective
   commit API, preserving unrelated staged work.
5. **Finalize the approved batch.** After the document commit, finalize approved
   items together. The tool validates the committed result before updating
   baselines. Commit finalized registry metadata separately when authorized.

If commits are withheld, preserve the reviewable changes and report the batch as
not finalized; do not bypass the committed-baseline requirement. Do not infer
commit authorization from skill invocation.

Record decisions, checks, document/registry commits and unresolved items in the
owning investigation. Report the exact unfinished stage after failure. Use the
tooling reference for recovery; do not reset baselines or repeat operations merely
to clear a warning.

`research-promotion` promotes supported reusable knowledge and methods.
`research-audit` evaluates research progress and priorities. Neither is a
prerequisite for organizational maintenance.
