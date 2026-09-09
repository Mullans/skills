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

The current schemas are lesson v3, evidence v2, and manifest v2. Existing lessons cannot be regenerated wholesale; ordinary changes are typed, intent-limited, hash-guarded patches. Existing recovery evidence can change only through an atomic interpretation patch whose references are revalidated against a bounded source-session rescan.

An OS-managed per-authority writer lock covers recovery through commit/rollback. Every mutation maps logical paths to one confined physical store, snapshots bytes and hashes, writes atomically, rebuilds derived state, validates the full result, and restores on failure. Exact no-ops create no journal and change no bytes.

Conflict activation is evaluated over the final manifest, not a prescribed resolution maneuver. A conflicting lesson may activate after contradictory guidance is retired/superseded or after scopes/exceptions are revised into demonstrable compatibility. Scope proof is deliberately conservative; retained conflict history prevents lifecycle transitions and replacement chains from erasing unresolved obligations.

## Delivery and host adapters

Dynamic delivery remains the default. Broad safety-critical guidance may be static, exact recurring procedures may become workflow skills, enforceable invariants may point to automation, and inactive material uses none. Local guidance supports dynamic/none only.

Codex and Claude use separate generated hook configurations and launchers but share one standard-library Python engine. Claude may share `AGENTS.md` only through a verifiable applicable `@AGENTS.md` import. Missing Python, stale catalogs, outstanding transactions, unreadable instructions, and unsupported hosts fail open to the manual compact index.

## Schema policy

This is the final development-only schema break permitted without migration support. The current code contains no compatibility validator or `migrate` command. Future incompatible schemas require an explicit version-specific migration mechanism. Such migrations are privileged record transformations and are not constrained to ordinary semantic lesson-patch intents.

## Deferred work

Deferred work includes Claude history scanning, cross-session comparative learning, explicit retrieval/application/outcome attribution, background mining, graph memory, embeddings, autonomous curation, global cross-project lessons, and automatic counterfactual generation. Recovery-miner precision on real Codex histories should be measured before adding architecture.
