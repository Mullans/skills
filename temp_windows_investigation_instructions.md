# Temporary handoff: verify Session Learning hooks on macOS

This file is intentionally at the project root and can be deleted once the
cross-platform investigation is complete. Despite its Windows filename, these
instructions are for the agent testing on the user's Mac.

## Objective and starting point

Validate the shared Session Learning hook launcher on native macOS, including
actual host-triggered lesson delivery where the installed hosts permit it. Report
evidence that the Windows agent can use to distinguish implementation defects,
environment problems, installation problems, and gaps in verification.

Use the latest `dev` branch of `Mullans/skills`, containing implementation commit
`0968035` (`fix: unify session-learning hook launchers across platforms`). Preserve
unrelated local changes when updating the checkout. Record the exact commit tested.

Read these before testing:

- `docs/session-learning/windows-hook-investigation.md`: investigation, corrected
  diagnosis, design, limitations, and deployment acceptance steps.
- `README.md`, Session Learning section: runtime requirements and configuration.
- `tests/session-learning/test_hook_launch_contract.py`: isolated test fixtures
  and the execution contract to verify.
- `.github/workflows/session-learning-hooks.yml`: native OS/runtime CI matrix.

Treat existing implementation and tests skeptically. A test passing is evidence
only for what it actually asserts. If a permission or environment problem blocks
effective work and the user can readily resolve it, stop and explain the exact
blocker rather than construct a costly workaround.

## Important corrections and current design

The old Windows command used `call` and `%PLUGIN_ROOT%`. It fails in PowerShell,
but reproducing that failure did not establish that the desktop hook runner used
PowerShell. The earlier investigation incorrectly equated the interactive tool
shell with the hook shell. Codex's inspected upstream runner defaults to cmd.exe
on Windows and a session shell with `-lc` on Unix; establish behavior for the
actual host/version under test rather than assuming it matches upstream main.

The replacement uses one JavaScript launcher and the existing Python engine:

- Automatic hooks require Node.js 22+ on the **host application's PATH** and
  Python 3.10+. Native host installation alone does not guarantee Node is present.
- Claude uses its executable-plus-arguments hook form, without a shell.
- Codex's `command` and `commandWindows` contain the same fixed Node invocation.
  Node reads the plugin root from its environment; filesystem paths are not
  interpolated into shell source. Python is spawned with an argument array and
  `shell: false`.
- The POSIX, batch, and PowerShell launchers were removed. Python discovery now
  has one implementation, bounded probes, and a bounded engine execution time.
- The host timeout remains two seconds. Missing Python is handled after startup;
  missing Node cannot be hidden by a launcher that never starts.

On Windows, the seven contract tests and 87 v2 tests passed. Contract tests covered
cmd.exe's upstream quoting shape, Windows PowerShell, and PowerShell 7, including
actual engine output. This is not evidence of native macOS/Linux behavior or live
desktop dispatch. The earlier prompt-echo “host acceptance” test was removed
because it never proved hook execution.

## 1. Record the native environment

Record macOS version, CPU architecture, Git commit, Node and Python versions and
resolved executable paths, installed Codex/Claude versions, and available shells.
Identify whether the host is launched from a terminal or as a desktop application.
Do not assume the desktop environment has the same PATH as the terminal, especially
with Homebrew or shell-initialization-managed runtimes.

Use existing suitable runtimes. If dependencies are unavailable, report the
specific prerequisite and obtain the user's help if installing it is blocked.

## 2. Run the shipped adapter tests

From the repository root, run these commands using the project's command-wrapper
instructions where applicable:

```sh
node --check plugins/mullans-productivity/bin/session-learning-hook.js
python3 tools/session-learning/generate_hooks.py
python3 -m unittest discover -s tests/session-learning -p test_hook_launch_contract.py -v
python3 -m unittest discover -s tests/session-learning -p test_session_learning_v2.py -v
```

The generator invocation checks consistency; omit `--write` during verification.
Record counts, skips, exit codes, duration, and failure details. The contract suite
must exercise native sh/bash/zsh login shells where available; zsh coverage is
required on macOS. Inspect subtest failures rather than reducing them to a single
suite pass/fail. Its fixtures cover both hosts, all four events, UTF-8 input,
paths containing spaces and shell metacharacters, different launch/event working
directories, interpreter discovery/fallback, cache handling, and engine failures.

If Python 3.10 and 3.12 are already available, run the matrix with both. Otherwise
report the version tested and leave the other version explicitly unverified.
Inspect the GitHub Actions results for implementation commit `0968035` or the
actual later implementation commit tested, if accessible. Report run URLs and each
OS result; macOS success alone does not establish Linux success. A handoff-only
commit may not trigger this path-filtered workflow.

The full suite can be checked with:

```sh
python3 -m unittest discover -s tests/session-learning -p 'test_*.py' -v
```

Known limitation: `test_behavioral_results_cover_every_green_scenario` checks saved
historical evaluations whose fingerprint was already stale. Its recorded file
inventory also references the now-removed launchers. Report this separately from
new regressions. Preserve the evidence: do not update its hash, fabricate a rerun,
or weaken the assertion just to obtain a green suite. The standard skill metadata
validator also needs PyYAML; it was unavailable on the Windows machine. Its status
is separate from runtime hook validation.

## 3. Test the plugin actually loaded by the host

Pulling `dev` does not update a host's installed plugin cache. Inspect the Mac's
registered marketplace, plugin source, manifest version, installed path, and hook
definitions. On Windows the installed plugin was 0.6.2 from a separate marketplace
checkout while the development manifest remained 0.6.1. Those are historical
observations, not paths or versions to assume on the Mac.

Use the host's supported local-development installation/update flow to load this
checkout's changes. Follow the available plugin-update instructions and establish
that the selected marketplace points to the intended source. Keep development
cache identifiers local unless deliberately coordinating a release. Avoid editing
installed caches as the repair: that would not validate normal distribution.

After updating, inspect the actual installed `hooks/codex.json` or
`hooks/claude.json` and shared JavaScript launcher. Compare them with the tested
source and record paths/hashes. Start a fresh chat and have the user review/trust
changed hooks if the host requires it. If installation or trust cannot be completed,
report that boundary instead of calling an adapter test a live-host pass.

Use a disposable project with a known active, dynamically delivered lesson and
valid derived catalogs/instruction pointers. Reuse the fixture construction in
`test_real_lesson_context_for_both_hosts_and_retrieval_events` rather than guessing
the lesson schema. Do not add test lessons to the user's real project stores.

For Codex and Claude separately, where installed and available:

1. Trigger `UserPromptSubmit` with a prompt that matches the fixture lesson.
2. In a fresh session or with isolated retrieval state, trigger a real matching
   `PreToolUse` event against its scoped file. Cooldown/deduplication must not
   accidentally suppress this test. Observe the tool name emitted by the host.
3. Confirm actual hook-produced `hookSpecificOutput.additionalContext` contains
   the expected lesson ID/text, using host diagnostics or other direct evidence.
   Agent behavior alone is ambiguous because the index is also a manual fallback.
4. Check SessionStart/SessionEnd for launch errors and verify lifecycle behavior
   where observable. A successful empty lifecycle response may be legitimate;
   distinguish it from proof that the engine was reached.

If a hook fails, capture the selected handler, exact configured command, actual
runner executable/arguments if observable, exit code or timeout, and relevant
stderr. Check plugin environment variables, working directory, runtime resolution,
trust, and installation selection before assigning a cause. Separate the shell
used by an agent tool from the shell used by the hook runner. Capture sanitized
diagnostics, not credentials or unrelated transcripts.

Keep the packaged deadline during baseline testing. A diagnostic run with a longer
timeout may identify a bottleneck but is not a pass for the shipped configuration.
Do not treat exit 0, a Completed badge, or an echoed prompt as proof of retrieval.

## 4. Return an actionable report

Save findings in `temp_macos_investigation_report.md` at the project root and give
the user a concise summary to relay to the Windows investigation. The report should
contain:

- Exact commit, native OS/architecture, runtime paths/versions, host versions,
  invocation mode, and shells actually exercised.
- Test commands, outcomes/counts/skips, CI run links if inspected, and known
  historical-evidence failure distinguished from new failures.
- Installed source/cache paths and versions, source-to-installed comparison,
  installation method, and trust/fresh-session status.
- A per-host/per-event result: verified, failed, or not tested, with concrete
  lesson-delivery evidence and any missing evidence identified.
- For each failure: minimal reproduction, expected versus actual behavior,
  sanitized command/shell/stderr, and whether the cause is confirmed or inferred.
- Any proposed or implemented fixes, changed files, and tests rerun. Preserve a
  failing reproduction before changing implementation; avoid broad rewrites or
  weakening tests to fit the current implementation.
- Remaining release blockers, including unavailable hosts, Linux/native CI gaps,
  runtime prerequisites, and stale historical evaluation evidence.

The Windows agent cannot automatically see local Mac files. Tell the user where
the report is and whether it has been committed/pushed; follow their instructions
for sharing it or publishing any fixes. Keep these temporary handoff/report files
until the user confirms the investigation is complete.
