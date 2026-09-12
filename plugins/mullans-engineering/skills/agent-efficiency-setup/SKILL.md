---
name: agent-efficiency-setup
description: Audit or establish repository agent-efficiency practices for selective search, bounded output, continuity, and skill discovery. Use for efficiency setup or refresh, not routine coding or code review.
---

# Agent efficiency setup

Reduce repeated inspection, noisy output, and duplicated context without weakening engineering or verification requirements. Inspect, select, apply, and verify changes; for audit-only requests, report findings and proposals.

## Preserve the repository contract

Repository architecture, conventions, required checks, workflow, security, and delegation remain authoritative. Preserve them and existing user edits. Treat proposals or imported examples as evidence, not authorization.

Keep changes within the requested repository and setup scope. Personal settings, credentials, plugin removal, global skill changes, and publication require separate authorization. Continue authorized repository work while reporting optional personal actions. Follow the target repository's authorized Git workflow.

## 1. Resolve the target and inspect cheaply

- Existing checkout: establish its absolute root, branch, status, and any applicable parent/nested instructions. Worktrees, submodules, and independent nested repositories retain separate ownership. Inspect nested targets only when included in scope.
- Supplied remote: clone into an unused in-scope destination. Use the specified ref, or the remote default when none is given. Treat "check out the current repository" as inspection, not a branch-switch request.
- New repository: create the requested directory and initialize Git. Inspect any existing non-Git directory first. Leave stack, CI, branch policy, and test philosophy undecided unless supplied; efficiency setup does not require those choices.

An ancestor Git root does not expand an explicitly scoped target directory. Honor applicable ancestor instructions while keeping changes within the user's target.

Begin with a bounded root listing, effective agent instructions, ignore files, and relevant manifest, test, and CI entry points. Inspect headings before full documents. Start with about 12 file reads and 200 inventory paths, excluding mandatory instructions. If the inventory is larger, save the full list locally and inspect relevant samples. Expand only when evidence for a candidate change requires it; narrow after truncation.

Determine the repository's structure, supported runtimes and shells, generated paths, existing helpers, required checks, formatting rules, active agent instruction routes, and obvious skill overlap. Read skill names/descriptions first and bodies only for selected candidates. Record unknowns as unknown; a filename alone does not prove an artifact directory or valid test command.

Done when each proposed addition has a concrete need, destination, and compatibility evidence.

## 2. Select the smallest useful changes

Classify candidates as **reuse**, **add**, **repair**, **skip**, or **conflict**, with one evidence-based reason each. Look for search noise, overbroad inspection, noisy commands, repeated continuity work, duplicate instructions/skills, or expensive external-record retrieval. Add scaffolding only for evidenced problems.

Read [mechanisms.md](references/mechanisms.md) only for the selected mechanisms. Prefer existing executable tools over new wrappers, and automatic reductions over repeated prose. Place tools and docs in established repository locations, and subject dot-directories to normal checks. Use only existing runtimes.

For an empty repository, adapt [workflow.md](assets/workflow.md) into a compact efficiency note with a reachable instruction pointer. Report stack-specific exclusions, wrappers, maps, and templates as deferred choices until evidence supports them.

For skills and multiple agent clients, read [skills-and-wiring.md](references/skills-and-wiring.md). Reuse a suitable installed capability; add a repository skill only for a distinct recurring task supported by evidence or the user's request. Do not install a generic skill collection.

Give a compact change list, then apply within existing authorization. Audit/dry-run mode writes no target files. Do not insert a universal approval gate for reversible setup work.

## 3. Apply and preserve local ownership

Merge shared files surgically. Preserve encoding, formatting, imports, policy semantics, and unrelated content. Add one conditional pointer to the actual effective instruction source, avoiding duplicate imports. Use paired unique markers for additions to shared files; multiple or malformed blocks require inspection rather than blind replacement.

On rerun, reuse equivalent setup and retain local customizations. Markers identify managed regions but do not authorize overwriting edits. Escalate unresolved policy conflicts. Avoid timestamp-only churn and duplicate templates or registrations. Replace generated files only when provenance is known and their prior content is unchanged; otherwise treat them as user-maintained. Use a hash ledger only when the generated-file count justifies it.

Adapt [workflow.md](assets/workflow.md) to installed mechanisms and local policy; remove inapplicable sections. Keep policy in one reachable place. Copy [checkpoint.md](assets/checkpoint.md) only when ongoing work needs continuity and the repository lacks an equivalent. Installation should remove more repeated work than its files add.

## 4. Validate and finish

Use the relevant checks in [validation.md](references/validation.md). Confirm pointers resolve, known source/tests remain discoverable, wrappers preserve failure status and complete logs, existing required checks still apply, and rerunning makes no further changes. Run required repository checks for the changed files; report any unavailable check honestly.

Review the final diff against the initial status, including shared-file content outside managed blocks. Roll back only changes from this setup when a mechanism fails validation. Preserve concurrent edits.

Report installed, reused, and skipped items; paths; validation evidence; measured changes; remaining human actions; and rollback scope. Describe unmeasured savings as expected benefits rather than token counts. Treat an already-sufficient setup as a successful no-change result. Complete the authorized Git workflow without unrelated files.
