---
name: session-learning
description: Use when explicitly invoked near the end of a coding session to preserve evidence-backed project lessons, reconcile prior guidance, and configure context-aware retrieval without retaining a transcript.
---

# Session Learning

Turn the visible session into the smallest project-local changes that can improve a future comparable task. Automatic hooks retrieve existing lessons; they never author or mutate canonical lessons.

**Core principle:** corrections and outcomes are evidence; persistent rules are conclusions. An uneventful session must change nothing.

## Retrospective

1. Read [references/decision-policy.md](references/decision-policy.md). Its gates, schemas, host routing, and write protocol are required.
2. Resolve the project root, recover any interrupted learning transaction, then inspect:
   - the visible session history or compaction summary and concrete tool/test/review outcomes;
   - applicable `AGENTS.md` and `CLAUDE.md` files;
   - `.agents/learning`, if it exists;
   - relevant repository-local skills and mechanical enforcement.
3. Use `scripts/session_learning.py search` to find related lessons. Compare each relevant lesson that was already active before this session and update only observable usage signals: eligibility, confirmation, violation, or repeat correction. The originating session is provenance for a new lesson, not usage of it.
4. Extract evidence events before proposing lessons. Do not ask the user to retell the session. Never reconstruct missing history or treat a plausible inference as evidence.
5. Gate, classify, reconcile, and route each candidate under the policy. Ordinary success, generic advice, praise, and transient task state are not lessons.
6. If the store is schema v1, run `migrate`, then `activate --host <active-host>` (or `both` only when explicitly configuring both hosts). Dynamic delivery is the default; reserve static delivery for broad, safety-critical, always-visible guidance.
7. Compute the full mutation as a manifest and apply it with `apply-manifest`. Do not make piecemeal learning-store or projection edits. The helper snapshots every target, replaces files atomically, rebuilds the index, validates, and rolls back on failure.
8. Run `validate --root <project-root>`. Repair any inconsistency before reporting success.

Invoke the helper as `python <skill-root>/scripts/session_learning.py <command>`. Relevant lifecycle commands are `search`, `audit`, `migrate`, `activate`, `set-delivery`, `deactivate`, `reactivate`, and `reconcile-delivery`. Use `reconcile-delivery --apply` only during this explicit retrospective or activation workflow.

## Boundaries

- Explicit invocation authorizes confident, localized learning updates inside the active project. It does not authorize unrelated implementation work, user-level memory changes, or edits to the installed skill itself.
- Preserve compact evidence contrasts, not raw transcripts.
- Never rewrite an instruction file, skill, or knowledge store wholesale. Modify only the related entry or managed block through the transaction helper.
- Never auto-resolve ambiguous conflicts. Keep the candidate `conflicted` and leave active guidance untouched.
- Create a workflow skill only when the session established an exact, recurring, successfully verified procedure. Otherwise record a candidate.
- Prefer an existing test, lint rule, generator, or type check over prose when it already enforces the invariant. Record proposed new enforcement; do not start building it during the retrospective.
- Treat automatic retrieval as advisory. Missing Python or unsupported hosts fall back to the compact index pointer; hooks fail open and retain only identifiers, counters, and timestamps in transient state.

## Result

If nothing passes the evidence gates, say that no evidence-backed lesson was found and that no files changed.

Otherwise report only:

- lesson IDs and their relation to existing knowledge;
- files updated, delivery mode, and whether each lesson is active, candidate, conflicted, superseded, or retired;
- measurement changes for existing lessons;
- informative deferrals or unresolved conflicts.
