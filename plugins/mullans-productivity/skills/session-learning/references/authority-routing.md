# Authority and Delivery Routing

Read before selecting/changing authority, equivalence, or delivery. Use [patch-authoring.md](patch-authoring.md) for a complete new-lesson payload.

## Choose one authority

| Authority | Use for | Store |
| --- | --- | --- |
| `project` | Repository facts, conventions, guardrails, workflows | `<project>/.session-learning` |
| `local` | Stable personal preferences or machine-specific rules for this project | Hashed personal project store under `~/.agents/learning/projects/` |

Keep evidence, provenance, relationships, conflicts, and cases in the same authority. Local guidance is not global memory and must not be projected into project instructions or committed. Use logical `.session-learning/...` paths in both authorities; the helper resolves the personal store.

Canonical and derived paths:

- `.session-learning/lessons/<lesson-id>.json`
- `.session-learning/evidence/<evidence-id>.json`
- `.session-learning/cases/<case-id>.json`
- `.session-learning/index.md`
- `.session-learning/retrieval.json`

## Choose delivery

| Mode | Purpose |
| --- | --- |
| `dynamic` | Default for scoped guidance retrieved as needed |
| `static` | Broad, safety-critical, always-visible instructions |
| `workflow` | Exact recurring verified repository-local skill; requires lesson kind `workflow` |
| `automation` | Existing enforcement target verified through decision policy |
| `none` | Inactive/evidence-only guidance |

Local lessons support only `dynamic` or `none`; local dynamic delivery has no instruction path. Candidates, conflicts, superseded and retired lessons require `none`, with every optional delivery field null.

Choose a non-workflow kind for dynamically retrieved rules. Active `workflow`-kind lessons require `workflow` delivery as a repository skill projection.

For project dynamic delivery, use an instruction-index pointer such as `AGENTS.md`. Static/workflow projections require a matching host and its native instruction/skill path; the engine manages their `session-learning:<lesson-id>` blocks. Claude may share `AGENTS.md` only through an applicable, verifiable `@AGENTS.md` import. Planned enforcement is a recommendation, not an automation target.

## Equivalence and retrieval

Leave `equivalence_key` null unless two lessons express substitutable guidance. A non-null lowercase stable key is unique among active lessons in one authority. When both authorities have applicable guidance with the same key, project guidance suppresses local guidance. Null keys do not suppress anything.

Routine search/index views omit retired and superseded lessons. Use `search --include-history` for explicit historical review; `--all` alone does not include them. Hooks retrieve active guidance without transcripts or canonical writes. Diagnose unavailable retrieval through `configure` and `audit` as described in [configuration-and-activity.md](configuration-and-activity.md).
