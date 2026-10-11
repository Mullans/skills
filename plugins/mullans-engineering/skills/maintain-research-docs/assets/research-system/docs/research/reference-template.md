# Research reference page and unit templates

Use these approximate shapes when creating or revising subject pages. Keep useful
technical details; omit fields with nothing material to say. Every factual claim
needs a source citation, individually or after a group wholly supported by the
same source. Replace the numbered placeholders below with real Markdown links to
precise source sections. Place citations beside the claims, not solely in a
page-wide bibliography. Link background optionally; do not require whole-document
reading to interpret ordinary reference entries.

The [wiki policy](../wiki.md) owns placement, splitting and organizational-review
policy. The [catalog convention](catalog/README.md#finding-convention) owns
existing finding IDs, evidence review and fingerprints. These examples are
templates, not findings. The maintenance parser recognizes their marked unit
headings; the catalog retains its existing finding-field schema.

## Page shape

```markdown
# Topic name

One or two sentences defining the reference question and objects covered.

## Scope

Applicable version/environment and shared conditions, with source citation [1].
Exact build identifiers belong here when needed to select valid bindings.

## Named reference family

One or more identifiable reference units using the shapes below.

## Related references

Optional links to related contracts, usage guides and supporting investigations.
```

Scope and related-reference sections do not count as units. Group headings also
do not count. Each finding block or explicitly identified contract/negative-result
block counts once. A table about one contract is one unit, not one unit per row.
Use stable identifiers; preserve existing finding identifiers when moving blocks.
The [maintenance tool](catalog/maintenance.md) recognizes `Finding ID: Title`,
`Contract ID: Title` and `Negative result ID: Title` headings outside fenced code.
A unit ends at the next heading of equal or higher level. Use uppercase letters,
digits and hyphens in IDs; do not nest reference units. Child descriptive headings
remain within their unit.

## Verified finding unit

Retain the catalog's field names and substantive review fingerprints.
Use the SHA256 returned by catalog `show` for the inspected supporting section;
an unchanged fingerprint proves unchanged support, not an accurate paraphrase.
Keep the statement and scope concise; basis explains support only as needed to
interpret the statement. Detailed receipts/chronology remain in investigations.

```markdown
### Finding PROJECT-SUBJECT-001: Short reference title

**Statement:** Confirmed behavior or relationship, with citation [1].
**Applies under:** Specific conditions beyond the page-wide scope.
**Basis:** Source citation [1]; brief support distinction if material.
**Limits and open issues:** Factual boundary, without speculative explanations.
**Review basis:** Substantive review date; source section and its SHA256.
**Relationships:** Relevant refinement/supersession links, if any.
```

Only verified, supported knowledge is promoted into reference pages. Preserve
provisional/challenged interpretations and their evidence in investigations;
catalog search may still discover those source records. A static binding is a
static fact, not proof of safe invocation or behavior in a running system.
Do not add a Standing field: verified-reference policy already establishes that
expectation. Applicability, limits and source-review warnings carry distinctions.

## Technical contract unit

```markdown
### Contract PROJECT-SUBJECT-CONTRACT-001: Object layout or interface name

**Applies under:** Additional version/object/lifetime conditions, if any.

| Binding / field | Verified meaning | Constraint |
| --- | --- | --- |
| Exact field, identifier or signature | Meaning | Material condition |

Source for all rows: [1]. Give individual rows citations when sources differ.

Confirmed ownership, linkage or calling relationships, with citation [2].
**Limits:** Unestablished behavior relevant to using this contract.
```

Include offsets, layouts, types, signatures, IDs and verified relationships when
useful for lookup. Preserve observed versus derived scope and unknown contracts.
Exclude how the experiment was scheduled, recorder status, capture costs and
rejected scans. Procedures for operating a tool remain in its usage guide.

## Scoped negative-result unit

```markdown
### Negative result PROJECT-SUBJECT-NEGATIVE-001: Specific construction and outcome

**Construction:** Exact authored change/mechanism and meaningful parameters [1].
**Applies under:** Conditions needed to delimit the result [1].
**Outcome:** Confirmed failed behavior, naming the checked object/registry [1].
**Limit:** What this observation does not establish.
```

A negative result must provide reusable technical knowledge, not merely report
an unsuccessful session. Include it when no relevant positive reference replaces
it. Once a verified positive construction answers the same reference question in
the relevant scope, promote that construction and cite earlier supporting evidence
where appropriate. Keep the original negative observation in its experiment.
Do not infer an untested cause or prerequisite from failure followed by success.

## Promotion and revision checklist

- Use [research promotion](../wiki.md#research-promotion) for current-session
  candidates, semantic review and collective conflict resolution.
- Each unit answers an identifiable reference question and has one owning page.
- Each factual sentence/table group has a directly supporting citation.
- Conditions distinguish static facts, observed behavior and derived relationships.
- Hypotheses, experiment procedure, session status and continuation stay outside.
- IDs, source sections and existing review fingerprints survive reorganization.
- Negative entries are checked against relevant later positive findings.
- New units receive stable markers before scripted unit counts are finalized.
