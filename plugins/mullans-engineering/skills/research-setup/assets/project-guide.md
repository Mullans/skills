# Project documentation

<!-- SETUP: Adapt paths and preserve established equivalents. Remove this note.
Keep the expansion table as directions, not links to nonexistent files. Add an
entry-links section for actual documents and update it as collections grow. -->

## Ownership

| Information | Owner |
| --- | --- |
| Purpose, scope, human entry points | Root README.md |
| Stable agent operating rules | AGENTS.md |
| Pending cross-session continuation routes | next-handoff.md |
| Handoff eligibility, pickup, publication and archiving | docs/handoffs/README.md |
| Session continuation snapshots | docs/handoffs/ |
| Question, method, observations, interpretation | experiments/ |
| Supported reusable facts and contracts | docs/research/ |
| Placement, promotion and splitting policy | docs/wiki.md |
| Reference units and citations | docs/research/reference-template.md |
| Evidence retrieval and coverage | docs/research/catalog/README.md |
| Research decisions, evidence interpretation, execution and closeout | docs/research/experiment-protocol.md |
| Numbered maintenance procedure and configuration | docs/research/catalog/maintenance.md and sibling JSON registries |
| Maintained code and reusable research logic | src/ or documented component roots |
| Runnable entry points and workspace maintenance | scripts/ |
| Checks for maintained code and methods | tests/ or documented component-local tests |
| Active inputs, captures, temporary logs, generated outputs | local/ |

A workstream is a sustained objective or theme. An investigation is a bounded
question and method; repeated runs or collection passes belong to that question.
Implementation tasks may use normal code and check records without manufacturing
an experiment for every edit. Link related investigations and implementation.

Keep one authoritative home for independently changing information. Linked
summaries and dated snapshots are useful; they are not competing current records.
Owning experiment or implementation records track current state and next actions.
The continuation index routes eligible work to another session.

## Find and grow

Every authored record needs a discovery route through an existing index or entry
page. Index entries contain a title, short scope description, and link so agents
can choose relevant material without reading every document. Include negative
and inconclusive investigations. Review navigation at about ten authored items,
or earlier when finding a record requires unrelated reading. Split only into
meaningful groups that reduce retrieval effort; terminal catalogs may be longer.
Keep one cross-session continuation index. Check links and inbound discovery when adding or
moving records. Preserve established evidence paths.

Use descriptive stable IDs: investigation start date plus a short slug, for
example `20260928-cache-persistence`; append `-02` for a collision. Titles may
improve without renaming paths. Handoff dates describe snapshot creation, with a
sequence suffix for multiple snapshots on a day.

## Add when needed

Agents can create these standard components when the trigger occurs. Propose new
top-level categories or migrations before changing established material.

| Trigger | Component and role |
| --- | --- |
| External sources need a maintained catalog | docs/references/: origin, version/date, relevance, access route and source notes |
| Reusable non-code procedures | docs/methods/: protocols, search/selection criteria and method versions |
| Multiple workstreams need stable maps | docs/projects/: scope, code and evidence routes; current status stays in owning experiment or implementation records |
| Sequencing or evidence-dependent decisions need a maintained view | docs/roadmap.md: dependencies and evidence gates, not duplicate session status |
| Local placement rules outgrow this index | docs/workspace.md: extract detailed ownership rules and link here |
| A language environment or concrete tool is needed | docs/toolchain.md: component/environment roots, setup and verified command entry points |
| Specialist external tool, repository or system install is adopted | third_party/README.md: role, location/access and usage links; PROVENANCE.md: upstream, license, adopted revision/version, acquisition/build and validation evidence |
| Machine-specific paths/configuration are needed | Ignored config/local.toml (or stack equivalent), with a shareable example |
| Concurrent work can interfere with a resource | docs/resource-checkout.md plus one authoritative ledger and helper |
| A recurring recovery procedure is established | docs/recovery/: verified steps and conditions |
| A report, package or application becomes an output | Choose a conventional, documented component/output location for the actual deliverable |

An evidence gate names a result that justifies the next stage and what happens
if it is not met. A roadmap is unnecessary until such sequencing matters.

Third-party distributions and cloned repositories can remain untracked while
their inventory and provenance are retained. Include tools installed elsewhere.
Record retrieval routes for a new machine, known access constraints, and whether
tools are merely located or actually validated. A local hash identifies bytes;
it is not authentication. Ordinary libraries are owned by dependency manifests
and lockfiles, not a second manually maintained catalog.

## Evidence and lasting knowledge

Use `local/` for working inputs and bulky or temporary artifacts; keep runtime
application caches separate from intentional investigation evidence. Respect access,
licensing and sharing constraints. Use [experiment protocol](research/experiment-protocol.md)
for research decisions, evidence interpretation, execution and closeout records.
Keep operating guidance about current procedures; put logs, historical narrative
and migration reports in owning experiment or implementation records.
When consolidating guidance, retain applicable information in its topic owner and
link it instead of duplicating it. Preserve unique evidence before removing a copy.

## Finding conventions

Record new research in experiments first. At supported reusable milestones use
`research-promotion`; use [wiki policy](wiki.md#research-promotion) for eligibility
and conflict review. Only supported facts and contracts belong in reference pages.
Keep history and unresolved interpretations in experiments, procedures in their
procedural owner, and current state in owning experiment or implementation records.

Use [reference formats](research/reference-template.md) for stable unit identities,
scope, evidence and review metadata. Use [catalog guidance](research/catalog/README.md)
to retrieve and reconcile prior evidence. Use [maintenance](research/catalog/maintenance.md)
and `maintain-research-docs` for numbered organizational review, proposals and
approved batches. These owners are established during setup, even with no findings.
Keep project-specific commands, inputs, thresholds and tool contracts in their
owning documentation/configuration; record adopted equivalent paths here.

## Continuation

Use [handoff lifecycle](handoffs/README.md) for eligibility, pickup, publication
and archiving. `next-handoff.md` routes eligible cross-session work to its snapshot.
Same-session plans and checkpoints stay in their owning records.

## Shared resources

When shared-resource coordination applies, the project's `docs/resource-checkout.md`
owns scopes, authority location, atomic claims, ownership verification, restoration
and release. Add it under the expansion trigger above and link the adopted procedure.
Standalone user tools retain their own identity and restoration protections.
