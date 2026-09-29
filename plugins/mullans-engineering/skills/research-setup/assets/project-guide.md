# Project documentation

<!-- SETUP: Adapt paths and preserve established equivalents. Remove this note.
Keep the expansion table as directions, not links to nonexistent files. Add an
entry-links section for actual documents and update it as collections grow. -->

## Ownership

| Information | Owner |
| --- | --- |
| Purpose, scope, human entry points | Root README.md |
| Stable agent operating rules | AGENTS.md |
| Current workstream status and immediate next action | next-handoff.md |
| Session continuation snapshots | docs/handoffs/ |
| Question, method, observations, interpretation | experiments/ |
| Maintained conclusions | docs/research/ when needed |
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
An experiment's next step describes its checkpoint, while the live index owns
what the workstream should do now.

## Find and grow

Every authored record needs a discovery route through an existing index or entry
page. Index entries contain a title, short scope description, and link so agents
can choose relevant material without reading every document. Include negative
and inconclusive investigations. Review navigation at about ten authored items,
or earlier when finding a record requires unrelated reading. Split only into
meaningful groups that reduce retrieval effort; terminal catalogs may be longer.
Keep one current-work index. Check links and inbound discovery when adding or
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
| First result useful beyond its investigation | docs/research/: subject findings and index; conventions stay in this guide |
| External sources need a maintained catalog | docs/references/: origin, version/date, relevance, access route and source notes |
| Reusable non-code procedures | docs/methods/: protocols, search/selection criteria and method versions |
| Multiple workstreams need stable maps | docs/projects/: scope, code and evidence routes; current status stays in next-handoff.md |
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

Use `local/` for working inputs and bulky or temporary artifacts, grouped by
investigation when useful. Create subfolders such as captures, analysis, samples,
backups, and builds only as needed. Keep runtime application caches separate
from intentional investigation evidence. References may be existing external
sources or the user's own research documents.

Documentation is the lasting record: preserve the method, relevant input/source
identity, observations, interpretation, and limitations needed to understand and
challenge a useful result. Attribute sources with relevant page/section pinpoints
and distinguish quotations, summaries, and what was actually examined. Appraise
source applicability rather than requiring local replication of every reference.

Record run/pass identity when repeating a procedure, method/code revision or
snapshot including relevant uncommitted changes, effective configuration, and
deviations. Use checksums where exact byte identity matters; use source versions,
dates, query/selection criteria, or evaluation tolerances where those fit better.
Keep originals unchanged while needed; create separate analysis or redacted
derivatives, identifying which artifact any checksum describes.

Active prerequisites may remain local; record their paths and how they were
collected or can be regenerated. Do not promise regeneration of transient data.
Retain small shareable excerpts or regression fixtures when they have continuing
value. Large resolved-error logs need not be permanently retained. Explain a
missing artifact only when it materially limits a maintained conclusion or next
action. Cleanup is separate from setup and handoff creation; neither authorizes
deletion. Respect access, licensing, and sharing constraints for every location.

Keep a durable error explanation when it can prevent recurrence, improve future
diagnosis, qualify an earlier finding, or preserve a non-obvious fix. Include
symptoms, cause, diagnosis/log-generation method where useful, fix, and verification.
Routine mistakes need no new lesson document. Promote useful tentative, negative,
and inconclusive results; durable means worth retaining, not permanently certain.

## Finding conventions

Promote a finding when it can change a future decision or prevent repeated work,
including useful negative or inconclusive results. Use this compact convention
per substantive finding; prose or a small table is sufficient:

| Dimension | Convention |
| --- | --- |
| Claim | What the evidence supports; distinguish an untested hypothesis explicitly |
| Scope | Subject and relevant build/version, corpus, configuration, conditions, and unexamined boundaries; omit irrelevant dimensions |
| Evidence basis | Observed: direct records or measurements. Source-reported: attributed external/user-source claims. Derived: stated reasoning from cited evidence. Combine as needed and link precise records. |
| Confidence | Tentative: material gaps or alternatives remain. Supported: adequate evidence within stated scope, with known limits. Strongly supported: relevant confirmation/checks substantially reduce plausible alternatives within scope. Give a short rationale. |
| Standing | Current unless marked contested, superseded, or withdrawn; link the reason and replacement where applicable |

Evidence type does not determine confidence. Local observations can be flawed;
references can be strong. No tier means universally certain. Record what change
or new evidence would require reconsideration when it matters.

Distinguish not tested, not detected under stated conditions, and evidence of
absence from a suitable method. A zero-match search supports only its documented
coverage. Preserve useful contrary evidence. When revising a claim, make the old
claim's changed standing and successor discoverable without leaving obsolete
advice presented as current. Avoid permanent verbose histories on every page;
link to the relevant investigation or historical record.

## Continuation

On a handoff request, reconcile relevant investigation and code/check records,
promote useful findings, then write a short snapshot using the local handoff
template. Include enough gist to resume and precise links for details already
easy to retrieve. Save and validate the snapshot before changing its index pointer.
Reread the index before updating only the selected row. Concurrent index writers
need serialized updates; atomic replacement alone does not prevent lost updates.
If safe publication is unavailable, keep the snapshot and report routing pending
instead of overwriting another session's work. On a quick-checkpoint request,
prioritize current state, pending risks, and next action;
mark reconciliation still owed. Never present an incomplete closeout as complete.

New projects use stable `docs/handoffs/<topic>-<date>[-sequence].md` paths. Resume
does not move them; a new snapshot supersedes the current pointer. Record meaningful
mid-session progress in owning records. Preserve historical snapshots. Completed
work with no follow-up leaves the live index but retains a route to its outcome.

Resume by reading the selected row, snapshot, and directly needed references.
Check relevant repository changes and immediate input availability. Reconcile
observed discrepancies; ask about material conflicts in scope or intent. Ordinary
resume is not a whole-project audit or automatic rerun of completed checks.

## Shared resources

Define exact physical/data scopes and incidental effects before introducing
coordination. Every contender, including separate checkouts, must use the same
authoritative state location; copied or Git-synchronized ledgers are not locks.
Use the documented helper to acquire all affected resources atomically as one
bundle. A persistent owner/claim ID is separate from the short-lived mutation guard.

Verify owner, claim ID, and affected scope immediately before live operations and
rollback. Hold the claim through final verification. Release only your own bundle
with a receipt for the agreed final state: restored data, or finished jobs and an
idle device/service as appropriate. The helper checks the receipt exists; the
operator checks its contents and actual state. Claims never expire automatically.

Unreadable ledgers, abandoned guards, or another owner's claims block relevant
live operations pending user recovery. Agents never remove those holds or copy
another session's identity to take over. Handoffs reference the authority but grant
no ownership. Helpers coordinate cooperative agents, not OS access or permission
to conduct experiments. Keep this machinery out of standalone user tools while
retaining the tools' own identity and restoration protections.
