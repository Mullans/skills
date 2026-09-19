# Session Learning Architecture Decisions

This maintainer document stays outside the distributable skill.

## Two canonical authorities

Project records live at `<project>/.agents/learning`. Personal, project-specific records live at `~/.agents/learning/projects/<sha256(normalized-project-root)[:16]>`. The latter never persist the raw root and never project into repository instructions. Evidence, provenance, relations, cases, and conflicts cannot cross authorities.

Each authority derives a human `index.md` and bounded `retrieval.json`. Hooks read at most those two catalogs and bounded applicable instruction surfaces; they never enumerate lesson records. Project guidance deterministically wins ties, while a local lesson is suppressed only by an applicable project lesson with the same explicit non-null equivalence key.

## Manual authoring, automatic reading

The explicitly invoked retrospective is the only authoring boundary. It may use visible current-session evidence and an optional read-only historical scan. Advisory hooks inspect the current hook payload and derived catalogs, inject relevant active guidance, and never inspect transcripts or mutate canonical lessons.

This remains a hook architecture rather than an MCP: lifecycle-triggered context injection is the needed behavior, while callable tools alone would not self-trigger retrieval.

## Scanner/analyzer separation

Host scanners own transcript discovery and schema adaptation. The host-neutral analyzer consumes compact normalized events in memory and emits hypotheses plus diagnostics. Neither writes canonical state.

The initial adapter supports bounded Codex JSONL histories. Claude scanning is deferred until its record variants and project-matching behavior have a dedicated fixture corpus. A normalized session `cwd` matches only the requested root or its descendants, preventing parent/monorepo leakage.

Malformed or consequential unknown records are causal barriers. User-authored items are opaque boundaries. The analyzer requires a decisive failure/repair/verification slice, causal correspondence, an observed behavior delta, no stronger intervening explanation, and the normal lesson promotion gates.

## Normalization-first privacy

Transcript values are normalized, allowlisted, bounded, and redacted before correlation or fingerprinting. Raw transcript text, normalized streams, commands, outputs, cursors, and failure-category hints are never persisted. Accepted recovery evidence retains only compact contrast, causal event IDs, behavior delta, fingerprints, and analyzer provenance.

Source identity is independent of interpretation: it hashes host, session, failure endpoint, and verification endpoint. Content identity hashes sanitized contrast, every causal role, and behavior delta. Analyzer version is separate provenance. This permits exact no-ops and explicit reinterpretation without creating duplicate evidence.

## Typed transactional mutation

The current schemas are lesson v4, evidence v2, and manifest v2. Lesson v4 separates structural `schema_version` from the `version` of the skill that last wrote the lesson. Existing lessons cannot be regenerated wholesale; ordinary changes are typed, intent-limited, hash-guarded patches. Existing recovery evidence can change only through an atomic interpretation patch whose references are revalidated against a bounded source-session rescan.

An OS-managed per-authority writer lock covers recovery through commit/rollback. Every mutation maps logical paths to one confined physical store, snapshots bytes and hashes, writes atomically, rebuilds derived state, validates the full result, and restores on failure. Exact no-ops create no journal and change no bytes.

`audit` is the complete health view and includes structural validation, migration candidates, store summaries, and hook error reports from one record-loading pass. `validate` remains a narrow pass/fail compatibility view over the same validation logic for scripts and tests.

Conflict activation is evaluated over the final manifest, not a prescribed resolution maneuver. A conflicting lesson may activate after contradictory guidance is retired/superseded or after scopes/exceptions are revised into demonstrable compatibility. Scope proof is deliberately conservative; retained conflict history prevents lifecycle transitions and replacement chains from erasing unresolved obligations.

## Delivery and host adapters

Dynamic delivery remains the default. Broad safety-critical guidance may be static, exact recurring procedures may become workflow skills, enforceable invariants may point to automation, and inactive material uses none. Local guidance supports dynamic/none only.

Codex and Claude use separate generated hook configurations and launchers but share one standard-library Python engine. Claude may share `AGENTS.md` only through a verifiable applicable `@AGENTS.md` import. Automatic retrieval is advisory: launchers return success even when Python or the engine fails. Real errors create no normal telemetry; they create one bounded report per SHA-256 identity with occurrence counts, current skill version, applicable lesson version/schema, and a relevant sanitized file path. Reports exclude prompts, tool arguments, lesson contents, commands, environment variables, credentials, and transcripts. `audit` presents them.

## Schema policy

Skill releases within the same major version must read and write lessons produced by every release in that major version. The installed skill owns the current schema target and ships a sequential migration registry; each step advances exactly one lesson schema version. Validation, audit, and derived catalogs normalize supported legacy lessons in memory, allowing new current lessons to coexist with them. Explicit authoring commits the requested lesson before offering migration. Migrations are optional, transactional, idempotent record transformations and may also update supporting evidence and derived catalogs required for full-store validity. Hooks never migrate because advisory retrieval cannot mutate canonical lessons.

A future lesson schema change must add and test a version-specific step before release. Records with missing, invalid, unsupported, or newer schema versions fail unchanged. Major skill releases may establish a new compatibility boundary, but must document the required upgrade path.

## Deferred work

Deferred work includes Claude history scanning, cross-session comparative learning, explicit retrieval/application/outcome attribution, background mining, graph memory, embeddings, autonomous curation, global cross-project lessons, and automatic counterfactual generation. Recovery-miner precision on real Codex histories should be measured before adding architecture.
