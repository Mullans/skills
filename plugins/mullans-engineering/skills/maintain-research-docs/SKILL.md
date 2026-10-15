---
name: maintain-research-docs
description: Audit research-reference organization, prepare maintenance proposals, or apply an approved batch using the research pipeline's wiki, catalog and batch-review system. Use for reference maintenance rather than current-session promotion.
---

# Maintain research docs

Route research-reference maintenance to its owning project documents and packaged
tools. `research-setup` establishes the standard paths; `research-promotion` handles
current-session milestone promotion.

## Choose the stage

Begin a new maintenance review with the existing maintenance audit. Prepare
proposals for flagged items without approval; when the concrete batch already
has human approval and execution authorization, validate and apply it without
requesting approval again. Skill invocation does not approve restructuring or
authorize a commit. Maintenance concerns organization; scientific verification,
capability audits and new experiments remain separate tasks. Direct text
corrections and requested policy edits need no organizational audit unless they
also change reference ownership, structure or accepted maintenance baselines.

## Load the owning guidance

The following standard paths are part of this pipeline, not arbitrary per-project
choices. Read project copies for configured values and adopted decisions. The
linked bundled assets supply the reusable policy and defaults that setup installs.
Prefer installed project owners; use bundled defaults when those owners are absent.
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
| `docs/research/experiment-protocol.md` - [experiment protocol](assets/research-system/docs/research/experiment-protocol.md) | Evidence interpretation and research execution requirements when substantive claims or new investigations are involved |

The experiment protocol owns proportionate checks and evidence recording;
maintenance safeguards apply to their named maintenance stages, not ordinary
research readiness. Use current adopted wiki/template decisions when older
wording differs. Report the discrepancy; keep unrelated policy/tool repairs outside the maintenance batch.
Setup installs the packaged tools under `scripts/workspace/`; use their interfaces
for discovery, measurements, source validation, selective commits and revision
discovery. Install missing infrastructure through the bounded setup/adoption step
only when the selected maintenance operation needs it. An ordinary text correction
does not require installing or auditing the research system. Run commands with
the project's recorded interpreter/execution prefix and retain their arguments and error semantics.

## Audit and propose

Follow the installed project's `docs/research/catalog/maintenance.md` under
`Audit and proposals` (bundled default linked above) to determine the measured review set, assess every flagged item and prepare concrete
proposals. Use the wiki for ownership/content decisions, the template for unit
shapes and the catalog for support checks. Present needed human decisions without
applying pending proposals or resetting accepted baselines.

## Apply an approved batch

Follow the installed project's `docs/research/catalog/maintenance.md` under
`Approved batch sequence` (bundled default linked above), within existing execution
and commit authorization. Its source validation, selective
document commit, atomic finalization, registry commit and closeout requirements
govern completion. Report the exact unfinished stage when a safeguard blocks it;
retain review history in the owning experiment rather than reference pages.
