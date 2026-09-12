---
name: make-it-so
description: Execute an approved implementation plan through validated completion. Use only when the plan is present in the conversation or a provided file and the user explicitly asks to implement it.
---

# Make It So

Implement the approved plan. The plan is in this conversation or in a file already provided; it is the source of truth for scope, requirements, and architecture. If no plan is present, stop and ask for it rather than reconstructing one.

## Setup

1. Establish the intended Git context before editing. Follow repository, harness, and `AGENTS.md` instructions for branches and worktrees. If no appropriate task context is already established, create a branch named for the plan. Use a separate worktree when it is the repository or harness convention, isolation from the current checkout is needed, or the plan calls for it. Preserve existing work: if uncommitted changes overlap planned work or their intent is unclear, stop and ask.
2. Run the fastest relevant existing tests and checks to establish a baseline. Baseline failures are not part of this effort unless they block verification of plan work; record them under follow-ups.
3. Break the plan into work units ordered by dependency and risk. Each unit should be small enough to verify and large enough to advance the implementation. Record the breakdown in the task list or a durable file so it survives context compaction.

## Implementation loop

For each work unit:

1. Inspect the relevant code, tests, tooling, and conventions before changing it.
2. Implement the unit, preferring existing abstractions and patterns. Introduce new structure only when the plan or concrete evidence requires it.
3. Run the most focused meaningful validation. Add or update tests when they demonstrate changed behavior or guard against a plausible regression.
4. Commit at coherent milestones with a message describing the completed work. Never push, rebase, amend, or force.

At integration points and after substantial architectural changes, run broader relevant validation and obtain an independent review of the diff since the last milestone. Give the reviewer the plan as well as the diff, so it can assess requirement coverage, correctness, regressions, architectural fit, and maintainability. Resolve substantive findings before continuing. A separate review is unnecessary for truly trivial changes.

## Delegation

Where the harness provides sub-agents, use them for independent workstreams, targeted investigation, and diff review. Parallelize only work with no overlapping edits or shared assumptions. Where the harness does not provide sub-agents, perform the same work in sequence; this is the expected fallback. You own integrating and reconciling everything into one coherent change.

## Scope

Stay inside the plan. Ordinary implementation details - naming, local structure, and choice among existing helpers - are yours to decide. Put unrelated issues, including unrelated test failures, under follow-ups rather than expanding this change.

## Decisions that need the human

Stop and ask when a choice would require an unplanned or materially different user-visible behavior, public interface, schema, or dependency; materially contradict the plan; or create a change that cannot reasonably be reversed within the current work unit.

Before asking, finish and commit every independent work unit that does not depend on the answer, then make a decision request containing the options, your recommendation, and what remains blocked. This is a mid-implementation pause: preserve the recoverable state and resume the same implementation effort after receiving direction. Record meaningful deviations from explicit plan decisions and their rationale; ordinary local implementation choices do not require deviation logs.

Until the Completion criteria are met, do not trigger workflow actions that represent task completion, including opening a PR, requesting final approval, merging, marking the task done, archiving it, or delivering a final implementation summary. Follow repository or harness-specific completion workflow only after completion.

## Completion

Review the full diff against the plan, resolve material findings, and run the full relevant validation. Then report:

- Branch name and commit list.
- What was implemented, by work unit.
- Meaningful deviations from the plan and why.
- Validation run and results, including anything skipped.
- How to verify manually.
- Follow-ups: out-of-scope issues found, remaining concerns, and suggested next work.
