# Session Learning v2 Architecture Decisions

This is maintainer documentation. It is deliberately outside the distributable skill because agents do not need it to run the retrospective or retrieval workflow.

## One project-local authority

Canonical records live in `<project>/.agents/learning` for every supported host. Versioned, one-record-per-file JSON keeps evidence reviewable, prevents cross-project leakage, and permits later migrations without discarding history. `index.md` is derived state.

## Manual authoring, automatic reading

`$session-learning` remains an explicitly invoked retrospective and is the only workflow that creates, reconciles, or changes lessons. Advisory hooks provide the automatic read path. They inspect only the current hook payload and canonical records, inject relevant active guidance, and never mutate lessons or read transcript files.

An MCP is not needed for v2: hooks provide lifecycle triggers and context injection, whereas an MCP would expose callable tools without making retrieval self-triggering.

## Dynamic delivery by default

Scoped guardrails and contextual knowledge use `dynamic` delivery. Broad, safety-critical, or explicitly selected guidance may use `static`; established procedures use `workflow`; mechanically enforceable invariants use `automation`; inactive material uses `none`.

Dynamic delivery avoids turning `AGENTS.md` or `CLAUDE.md` into an ever-growing lesson dump. A compact index pointer remains as the manual and no-Python fallback. Static markers suppress dynamic delivery only when the active host verifiably loads the containing instruction surface.

## Host adapters, shared semantics

Codex and Claude use separate hook configurations because event schemas and tool names differ, but both delegate matching and state behavior to one standard-library Python engine. A repository-level generator owns the shared event table and renders both configurations inside `plugins/mullans-productivity`. Claude's cross-platform Node dispatcher selects the optional Python runtime; Codex uses its POSIX/Windows command overrides directly.

The same nested directory is the distributable plugin boundary for both hosts. Its Codex and Claude manifests explicitly select `hooks/codex.json` and `hooks/claude.json`. No default `hooks/hooks.json` exists because Claude merges default and manifest hook sources; distinct explicit paths prevent cross-host schema discovery while preserving one canonical `skills/` tree. The repository-root marketplace catalogs point to this directory, so maintainer-only `docs/`, `tests/`, and `tools/` are not copied into installed plugins.

When a project intentionally shares `AGENTS.md`, Claude visibility is established with a minimal `CLAUDE.md` containing `@AGENTS.md`. Lesson bodies are never mirrored into both files. Unknown hosts retain canonical records and the pointer but receive no invented automatic conventions.

## Transactional mutations

Every multi-file authoring or delivery change uses one transaction layer: validate the intended delta, snapshot original bytes and hashes, atomically replace targets, regenerate the index, validate the complete result, then remove the journal. Failed or interrupted mutations restore the snapshots. Hook state uses separate atomic JSON replacement and is always non-authoritative.

## Privacy, cooldown, and isolation

Hook state is keyed by project-root hash and host session ID. It contains only schema version, counters, delivered lesson IDs, and timestamps—never prompt text, command text, raw paths, or transcripts. Same-turn deduplication plus a five-user-prompt cooldown limits repeated context, while compaction and resume may bypass cooldown because prior context can have disappeared.

## Runtime dependency and failure mode

Automatic retrieval optionally requires Python 3. Each host adapter may first read an absolute interpreter path from the project or personal retrieval configuration, but it accepts only an executable path and never a command string. Fixed launcher candidates are then probed, and only a selected fixed identifier—not an arbitrary or configured path—is cached in the host's plugin-data directory. Prompt and tool hooks fail open when Python is unavailable; session start emits one concise warning and the manual skill plus index remain usable. Hook work has a two-second timeout and bounded output.

## Bounded observability

The retrospective can use only visible session history or compaction summaries plus repository and execution evidence. It does not reconstruct missing early context. V2 records observable eligibility, confirmation, violation, and repeat correction; it still does not claim counterfactual helpfulness or reliable retrieval measurement.

## Coexistence and deferred infrastructure

Claude auto memory is a separate private, machine-local system. This skill never inspects or modifies it; project-versioned evidence gates and cross-host records remain the differentiator.

V2 defers `.claude/rules/`, embeddings, background lesson creation, global or cross-project promotion, automated test generation, and MCP infrastructure. The delivery object, stable IDs, and versioned schemas leave room for these without replacing the canonical store.
