# Authority and Delivery Routing

Read this reference before selecting or changing authority, equivalence, or delivery.

## Canonical stores

- `project`: `<project>/.agents/learning`
- `local`: `~/.agents/learning/projects/<sha256(normalized-project-root)[:16]>`

The normalized root is fully resolved, separator-normalized, and case-normalized where the host filesystem requires it. Local records and derived files never contain the unhashed project root. A local manifest still uses logical paths such as `.agents/learning/lessons/<id>.json`; the transaction mapper resolves them inside the hashed local store and rejects projections or path escape.

Choose `project` for repository facts, conventions, guardrails, and workflows that should travel with the repository. Choose `local` for a user's stable personal preference or machine-specific working rule for this project. Do not create global cross-project guidance. Evidence, provenance, relationships, conflicts, and cases remain within one authority.

Explicit retrospective invocation authorizes both stores for the active project. Missing stores remain absent until an accepted record is written.

## Current records

Lessons use `schema_version: 3` and require `authority`, nullable `equivalence_key`, `conflict_targets`, and monotonic `conflict_history` in addition to title, statement, kind, status, scope, triggers, anti-pattern, safe path, exceptions, delivery, provenance, relationships, usage, and timestamps.

Evidence uses `schema_version: 2` and requires `authority`. A `recovery_pair` additionally requires bounded `source` metadata and `behavior_delta` described in [history-mining.md](history-mining.md).

Canonical record and derived paths are:

- `.agents/learning/lessons/<lesson-id>.json`
- `.agents/learning/evidence/<evidence-id>.json`
- `.agents/learning/cases/<case-id>.json`
- `.agents/learning/index.md`
- `.agents/learning/retrieval.json`

This development schema is authoritative. There is no compatibility or migration command.

## Equivalence

`equivalence_key` defaults to `null`. It is an explicit reconciliation artifact, not a topic taxonomy. Set or reuse a lowercase stable key only when two lessons express substitutable guidance.

A non-null key is unique among active lessons within one authority. Project and local lessons may share it. During retrieval, an applicable project lesson suppresses an applicable local lesson only when both have the same non-null key. Null keys never suppress each other.

## Delivery

Project lessons may use:

- `dynamic`: default for scoped guidance; retrieved from the catalog and backed by the compact index pointer;
- `static`: broad, safety-critical, explicitly always-visible instruction guidance;
- `workflow`: an exact recurring verified repository-local skill;
- `automation`: a recorded enforcement target;
- `none`: inactive or evidence-only material.

Local lessons may use only `dynamic` or `none`, and local dynamic delivery has no instruction path. Local content is never statically projected, committed, or copied into project instructions.

Candidates, conflicts, superseded lessons, and retired lessons use `none`. Each static/workflow project projection contains `session-learning:<lesson-id>`. Dynamic project guidance maintains one `session-learning:index` pointer. Claude may treat `AGENTS.md` as visible only through an applicable, verifiable `@AGENTS.md` import.

## Retrieval catalogs

Each authority derives `index.md` and `retrieval.json`. The catalog contains only active matching/injection fields, sorted by lesson ID, with at most 2,000 entries and 1 MiB canonical JSON. Overflow fails and rolls back the mutation; it is never truncated.

Hooks read at most the project and local catalogs, never individual lessons or transcripts. They skip an oversized, invalid, stale, unreadable, or transaction-in-progress authority and fail open. Live instruction visibility checks are separately bounded.

Matching ranks path/scope overlap, exact normalized triggers, operation terms, then supporting lexical relevance. Project results win deterministic ties. Injected context includes authority, ID, the complete statement, safe path, and every exception; a lesson is skipped rather than truncating qualifiers. Same-turn deduplication and the five-user-prompt cooldown apply to the authority-qualified identity.
