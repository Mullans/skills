# Selective mechanisms

Read only the sections matching observed needs. These are implementation criteria, not a mandatory bundle.

## Search boundaries and inventory

Use Git's tracked-file inventory for ownership and ripgrep's searchable inventory for search scope. They differ: `.ignore` affects ripgrep, not `git ls-files`; Git exclusions do not hide already tracked files from Git's inventory. Include untracked source when needed. A root tracked-file listing does not inventory independent nested clones or submodule contents.

Inspect `.gitignore`, `.ignore`, `.rgignore`, and relevant nested overrides before adding anything. Prefer scoped search commands when uncertain paths might contain authored content. Exclude only confirmed disposable/generated paths with anchored patterns where practical. Names such as `build`, `dist`, `bin`, `vendor`, `fixtures`, or `data` do not establish disposability. Keep authored fixtures, snapshots, migrations, schemas, vendored patches, and tests discoverable. Do not generate a blanket ecosystem ignore matrix.

Search-only exclusions also affect human searches. `.git/info/exclude` changes Git's treatment of untracked files and is not a substitute for uncertain search exclusions. Add Git exclusions only for generated artifacts created by this setup, preserving existing tracking decisions.

Check actual search behavior, including higher-precedence `.rgignore` rules, hidden files, and current working directory. No results means no matches in that scope, not proof of repository-wide absence. For absence checks, consult tracked paths and use scoped `rg --no-ignore --hidden` or explicit files; retain a `.git` exclusion. Do not rerun an unrestricted root search with all ignores disabled.

Add an inventory helper only if direct commands are insufficient. Its contract: explicit root/scope, tracked/searchable modes distinguished, optional untracked files, bounded output with a visible omission count, and no traversal through symlinks/junctions into sibling repositories. Git-unavailable or empty-repository fallback is a shallow explicit listing. Do not install a new language runtime just to enumerate files.

## Command output

Reuse a working summarizer, including existing RTK filtering where configured. Otherwise generate a small helper in an available, supported runtime only for demonstrated noisy commands. Native bounded tool output plus durable logs may already suffice.

Required wrapper behavior:

- Run the exact executable and argument vector in the intended cwd; preserve the command's environment and exit status. Avoid shell-string interpolation. Document explicit shell invocation for shell builtins or Windows command shims.
- Stream stdout and stderr to collision-safe logs in an existing artifact location, using bounded memory and bounded displayed characters as well as lines. Long single-line output must not defeat the limit.
- Return status, log path, recognized aggregate counts, bounded failure evidence, and a short tail. Unknown output stays unknown: a successful parser is not a successful command. Do not treat a text match for "error" as an exit code.
- Preserve failure, launch failure, and interruption distinctly. Report incomplete logs, write errors, and timeouts; never claim complete capture when it failed. Background/interactive commands require separate handling rather than this wrapper.
- Keep original logs local under the repository's existing artifact/retention rules. Do not upload logs or expose environment variables in summaries.

Suggested output budget: 30 lines on success, 60 on failure, each additionally capped at about 8,000 characters overall. Adapt to existing tool constraints. Save full evidence even when display is truncated.

Validate with a harmless fixture command before using a wrapper for real verification. Required tests remain required, including broad suites at every gate already mandated by the repository. Focused tests are additional iteration evidence, not a replacement. Change-to-test mapping is optional only when an existing reliable mapping is available; label heuristic selections incomplete.

## Continuity and delegation

Reuse existing plans and handoff formats. Add a compact checkpoint template only for long or interrupted work; include repository/branch/HEAD, worktree ownership, completed outcomes, exact verification evidence, outstanding requirements, and next action. Keep checkpoint instances task-specific so concurrent work does not overwrite one shared state file. Link durable documents instead of copying them. Verify cached state against Git before resuming.

An implementation manifest is useful when repeated scope discovery is observed: outcome, owning paths, acceptance criteria, source links, focused checks, and unchanged required gates. Do not require one for every edit.

Keep the repository's delegation permissions, concurrency limits, and review obligations. Where delegation is already authorized, reduce duplicate inspection using a bounded evidence packet: task, base SHA, scope, relevant paths, acceptance criteria, verification, and expected result. Do not impose FoundryHub's agent count or review policy on another repository. Avoid repeated polling and repeated full reviews where local policy permits.

## External records and maps

Use an already connected tracker with narrow project/status/ID filters and summary fields. Fetch full records only when needed for a live decision. Cache IDs and stable acceptance criteria in existing task records; refresh changeable state before acting on it. Setup does not authorize sending messages or changing tickets.

A compact repository map earns its maintenance cost only when repeated expensive navigation is demonstrated. Prefer links to existing manifests/workspace config. If created, identify its source and regeneration/invalidation procedure. Do not infer architectural responsibilities from directory names.
