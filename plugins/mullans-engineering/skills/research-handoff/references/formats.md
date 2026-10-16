# Handoff formats

Read when creating or adapting infrastructure. Existing project conventions take
precedence; this reference owns file shapes and portability. The project's
`docs/handoffs/README.md` owns lifecycle and eligibility.

## Infrastructure assets

| Asset | Default project destination | Role |
| --- | --- | --- |
| [Lifecycle](../assets/lifecycle.md) | `docs/handoffs/README.md` | Eligibility, pickup, creation, publication and archiving |
| [Snapshot](../assets/handoff.md) | `docs/handoffs/TEMPLATE.md` | Context needed by a later session |
| [Index](../assets/next-handoff.md) | `next-handoff.md` | Routes to pending cross-session snapshots |

Research setup may prepare these files without performing a closeout. Adapt only
needed infrastructure and link the index from an existing project entry page.

## Index columns

| Column | Meaning |
| --- | --- |
| Topic | Human-readable overarching objective or workstream |
| Status | Brief continuation condition or dependency |
| Follow-up document | Relative link to the selected snapshot |
| Next action | Required unfinished step and immediate prerequisite |

Keep the index as navigation and omit illustrative rows from generated indexes.

## Snapshot shape

Use the snapshot template and omit unused fields.

## Links and portability

Resolve links from each generated file's actual location. Generated documents
link to local project owners rather than installed skill files. If needed context
has no owning record yet, include the immediate context in the snapshot.
