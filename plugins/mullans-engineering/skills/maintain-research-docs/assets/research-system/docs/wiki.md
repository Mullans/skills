# Research reference policy

Use this policy for documentation ownership, reference authoring and promotion.
The [research index](research/README.md) owns subject navigation.

## Placement rules

| Content | Owner | Writing style |
| --- | --- | --- |
| Supported findings, structures, relationships and applicability limits | Maintained subject reference | State facts directly with scope and essential limits beside the claim |
| Reusable operating instructions and normal configuration | Workflow/tool guide | Use imperative steps and necessary configuration; route special cases to their owners |
| Tool internals, integration APIs, algorithms and schemas | Implementation reference or owning module | Explain contracts needed for implementation or diagnosis |
| Run-specific setup, observations, hypotheses and history | Experiment record | Record actual conditions, evidence, interpretation and outcome |
| Subject or command discovery | Index | Route to owners without repeating their content or maintaining another queue |
| Fields to complete | Template | Supply fields and examples without repeating procedure |
| External reports and techniques | External-reference collection | Preserve attribution, applicability and limitations |

Place content by purpose. A verified scientific relationship or data layout is a
research fact; how a tool measures or manipulates it is an implementation
contract. Promote reusable methods and limits to central owners. Experiments
remain provenance, not the only home of a useful operating method.

## Reference authoring

### Reference purpose

Make each unit sufficient for ordinary reuse within its stated scope. Researchers
may rely on maintained facts without routinely rereading raw investigations.
Follow original evidence for additional detail, a contradiction or a specific
support concern. Source links provide justification, not missing qualifications.

Keep statements and titles within the evidence's strength. Put essential limits
beside the claim. Keep hypotheses, unconfirmed causes, temporary status and trial
history in investigations; retain useful supported structures, interfaces and
scoped negative results.

Use the [reference template](research/reference-template.md) for unit shapes and
the [catalog convention](research/catalog/README.md#finding-convention) for support
metadata. Preserve IDs, substantive review dates and fingerprints during mechanical
moves or link repairs. Review changed claims before updating their review basis.

### Documentation style

- Give each fact or instruction one owner.
- Keep procedures focused on normal operation and necessary configuration.
- Put implementation and uncommon diagnostic details behind conditional pointers.
- Use lists for sequences and tables for comparisons, mappings and fields.
- Arrange procedural reading from entry point to required detail without upstream
  read loops.
- Remove summaries that repeat units below them; avoid duplicate catalogs and
  manually maintained finding databases.

### Citations and evidence

Cite authored research claims to supporting sources and specific sections. A
citation can support a group or table when it supports every fact; mixed-source
facts need their own citations. This is an authoring requirement, not a recurring
validation step for ordinary reuse.

Preserve scoped negative results unless a supported positive result supersedes
them for the same question and conditions. Do not infer a cause or prerequisite
that the observation did not isolate. Preserve original observations in their
investigations.

### Research promotion

1. Select supported, reusable knowledge from the owning investigation; promotion
   may yield no qualifying changes.
2. Review new or substantively changed claims against decisive evidence and
   applicability limits. Mechanical moves do not reopen scientific validation.
   Seek independent review only for a consequential claim the session agent
   cannot adequately verify; hold only affected claims if it is unavailable.
3. Use `research-promotion` to place findings and reconcile existing knowledge
   using the table below.
4. Check affected links, metadata or support. Ordinary promotion leaves
   organizational baselines unchanged.
5. Keep promotion history, decisions and unresolved issues in the investigation,
   rather than maintained reference content.

| Situation | Action |
| --- | --- |
| Refinement or additional supported scope | Update the owning unit with supported conditions and limits |
| Clear supersession in the same question/scope | Replace the claim while preserving original observations and relevant provenance |
| Unresolved contradiction | Hold affected claims/dependencies, add a precise source-linked warning and present conflicts together for user resolution |
| Independent uncontested finding | Proceed without waiting for unrelated conflicts |

Reconcile active direct consumers of a contradicted claim before relying on it
again. Mark unsupported extensions as hypotheses or remove their dependency;
trace further descendants only for a consequential dependency.

### Organizational review

Split when distinct questions need independent owners and cannot be reached
effectively through headings. Size alone does not mandate splitting.

Use `maintain-research-docs` for organizational audits and approved restructuring.
The [project maintenance guide](research/catalog/maintenance.md) supplies local
commands and configuration. Organizational acceptance does not certify technical
claims. Apply required user decisions for policy changes or substantial
restructuring within the project's authorization.

Move complete units, repair active incoming links and remove obsolete pages
without compatibility gateways or legacy anchors. Preserve dated requests and
investigation history rather than rewriting them as current procedure.
