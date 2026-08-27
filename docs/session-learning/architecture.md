# Session Learning v1 Architecture Decisions

This repository document records development decisions; it is not part of the distributable runtime skill.

## Project-local canonical state

Canonical records live in `<project>/.agents/learning` even when the active agent is not Codex. This keeps evidence and lifecycle state versioned with the project, avoids cross-project leakage, and gives both host adapters one source of truth.

## Native projections

The canonical store is not itself assumed to be auto-loaded. Active guardrails, index pointers, and workflow skills are projected only into the active host's native files. Do not mirror into both Codex and Claude files automatically; duplicated projections would create two authorities to reconcile.

## Incremental files

Each lesson, evidence event, and optional regression case has its own versioned JSON file. `index.md` is generated. This makes localized updates and reviewable diffs the normal case and leaves room for later schema migrations without replacing the v1 history.

## Conditional initialization

Do not create `.agents/learning`, an index, or instruction-file markers until at least one evidence-bearing lesson or informative candidate must persist. A no-op retrospective must be filesystem-neutral.

## Observable measurement only

V1 measures whether an active lesson was relevant, confirmed, violated, or corrected again in the session being reviewed. It does not claim to measure retrieval, application, helpfulness, or counterfactual benefit without a future read hook.

## Explicit invocation and bounded context

The skill is manual-only. It can analyze only session history or compaction summaries still visible to the active agent plus repository and execution evidence. Missing early context is not reconstructed; uncertainty lowers or prevents persistence.

## Deferred infrastructure

V1 does not include global memory, embeddings, background retrieval hooks, automatic test generation, periodic pruning, or cross-project promotion. The versioned schemas and stable IDs allow those capabilities to be added without discarding the initial records.
