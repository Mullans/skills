# Research reference page and unit templates

Replace placeholders with scoped facts and actual relative source links.

| Unit | Use for | Shape |
| --- | --- | --- |
| Finding | A supported conclusion | Six nonempty finding fields, including review metadata |
| Contract | A supported structure, binding or interface relationship | Bindings, conditions, sources and limits |
| Negative result | A failed construction under specific conditions | Construction, applicability, observed outcome and limit |

All three heading forms identify reference units. Only findings use the structured
catalog finding fields; contracts and negative results retain their lighter shapes.

## Page shape

```markdown
# <Topic name>

<Reference question and objects covered.>

## Scope

<Applicable environment, version, population or shared conditions.> [Source section](PATH#ANCHOR)

## <Named reference family>

<Reference units.>

## Related references

<Optional links to contracts, usage guides and supporting investigations.>
```

- Preserve existing IDs. New IDs start with an uppercase letter, followed by
  uppercase letters, digits or hyphens.
- Keep reference units as peers rather than nesting them.
- Keep all six finding fields nonempty. Use `Page scope` for no additional
  conditions and `None` for no relationship.

## Verified finding unit

```markdown
### Finding PROJECT-SUBJECT-001: <Scoped conclusion>

**Statement:** <Supported behavior or relationship.> [Source section](PATH#ANCHOR)
**Applies under:** <Additional conditions, or Page scope.>
**Basis:** [Source section](PATH#ANCHOR) <Support distinction, if material.>
**Limits and open issues:** <Factual evidence boundary.>
**Review basis:** YYYY-MM-DD; [Source section](PATH#ANCHOR) sha256=SECTION_SHA256
**Relationships:** None
```

Use the substantive review date and section fingerprint returned by the catalog
for `Review basis`. Replace `None` with refinement/supersession links when applicable.

## Technical contract unit

```markdown
### Contract PROJECT-SUBJECT-CONTRACT-001: <Structure or interface>

**Applies under:** <Additional environment/object/lifetime conditions, or Page scope.>

| Binding / field | Verified meaning | Constraint |
| --- | --- | --- |
| <Field, identifier or signature> | <Meaning> | <Material condition> |

Source for all rows: [Source section](PATH#ANCHOR)

<Supported ownership, linkage or calling relationship.> [Source section](PATH#ANCHOR)
**Limits:** <Unestablished behavior relevant to this contract.>
```

For mixed-source bindings, put the appropriate source link in each row.

## Scoped negative-result unit

```markdown
### Negative result PROJECT-SUBJECT-NEGATIVE-001: <Specific construction and outcome>

**Construction:** <Change/mechanism and meaningful parameters.> [Source section](PATH#ANCHOR)
**Applies under:** <Conditions delimiting this result.> [Source section](PATH#ANCHOR)
**Outcome:** <Observed failure and object or population checked.> [Source section](PATH#ANCHOR)
**Limit:** <What this observation does not establish.>
```
