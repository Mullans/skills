# macOS Session Learning hook investigation — 2026-09-26

## Tested source and environment

- Checkout: `dev` at `751083890597581cf2e9511c5f81d0e0c29fa308` (`7510838`, handoff). It contains launcher implementation commit `0968035`. The checkout was clean before this investigation. `git ls-remote origin refs/heads/dev` later confirmed that the tested commit still matched remote `dev`.
- Host: macOS 26.5.2 (build 25F84), Darwin 25.5.0, Apple Silicon `arm64`. Investigation ran in the ChatGPT desktop app 26.924.22138; fresh host trials used its bundled Codex CLI 0.158.0-alpha.2.1. Claude desktop app 1.3561.0 exists, but no `claude`/Claude Code CLI was found.
- Terminal/CLI PATH resolves Node v24.12.0 at `/Users/seanmullan/.local/share/mise/installs/node/24.12.0/bin/node` and Python 3.14.4 at `/opt/homebrew/bin/python3`. Fresh Codex CLI sessions actually launched the hook and reached Python, establishing runtime availability for those invocations. `launchctl getenv PATH` returned no value; the terminal PATH alone is not evidence for GUI launches. This desktop chat later received a dynamic project lesson after the user trusted hooks, but an isolated desktop fixture was not run.
- Native test shells: `/bin/sh`, `/bin/bash`, `/bin/zsh`, each invoked by the contract suite with `-lc`. The live CLI's shell tool used `/bin/zsh -lc`; this is the agent tool shell, not direct evidence of the hook runner shell. Python 3.10 and 3.12 were not installed in the checked locations or `mise`; only 3.14 was tested.

## Adapter and suite results

All commands were run from the repository root with the required `rtk` wrapper. Exit status and duration are from the local run.

| Check | Result |
| --- | --- |
| `node --check plugins/mullans-productivity/bin/session-learning-hook.js` | Exit 0, no diagnostics |
| `python3 tools/session-learning/generate_hooks.py` (without `--write`) | Exit 0, ~1.0 s; generated definitions consistent |
| `python3 -m unittest discover -s tests/session-learning -p test_hook_launch_contract.py -v` | Baseline exit 0, 7/7, no skips, 5.25 s suite / 6.47 s wall. After the test fixture edit, exit 0, 7/7, 5.97 s suite / 6.21 s wall. Exercised native sh/bash/zsh for Codex plus Claude exec-form simulation, four events, real lesson delivery, Unicode and metacharacter paths, interpreter fallback, cache, and engine failure cases. The subtests reported no failures. |
| `python3 -m unittest discover -s tests/session-learning -p test_session_learning_v2.py -v` with ordinary macOS `TMPDIR=/var/folders/...` | Exit 1, 87 tests, 7 failures and 5 errors, 2.71 s suite. Ten cases were caused by `/var/folders` versus canonical `/private/var/folders` path comparisons. Two cases failed the stale `first["changed"] is True` expectation below. |
| Same v2 command with `TMPDIR=/private/var/folders/bb/n6lw4llj55n5rz66b32vg65m0000gn/T/` | Exit 1, 87 tests, 2 failures, no errors or skips, 2.09 s suite / 2.39 s wall. Both are inherited runs of `test_current_schema_activation_is_idempotent` (HookTests and StorageTests): its fixture already has schema 3, valid dynamic delivery, pointer, and rebuilt index, so `activate_store` reports `changed: false` on the first call. This is a stale assertion, not a launcher failure. |
| Full `test_*.py` suite with canonical TMPDIR | Exit 1, 188 tests, 2 failures and 1 error, 8.02 s suite / 8.53 s wall. The two failures are the same stale v2 assertion. `test_behavioral_results_cover_every_green_scenario` errors because its saved inventory includes removed `plugins/mullans-productivity/bin/session-learning-hook`; this is the previously documented historical-evaluation evidence gap. |
| v2 suite after test fixture edit, ordinary macOS TMPDIR | Exit 0, 87/87, no skips, 2.11 s suite / 2.36 s wall. |
| Full `test_*.py` suite after test fixture edit, ordinary TMPDIR | Exit 1, 188 tests, no failures, one historical-evidence error as above, 7.59 s suite / 7.94 s wall. |

The macOS temp-path reproduction is: `Path(tempfile.mkdtemp())` begins with `/var/folders/...`, while storage code resolves the same path to `/private/var/folders/...`; a fixture then calls `path.relative_to(self.root)` or compares unresolved/resolved paths. Expected: assertions use equivalent canonical roots. Actual: `ValueError: ... is not in the subpath ...` or a path equality failure. Windows CI showed the analogous short-path alias `C:\Users\RUNNER~1` versus `C:\Users\runneradmin`. The fixture now resolves its temporary root before constructing project/home paths. The already-current activation fixture now expects `changed: false` on both calls. Product code and the two-second hook deadline were not changed.

## Native CI at implementation commit 0968035

[Workflow run 36266231221](https://github.com/Mullans/skills/actions/runs/36266231221) completed with all six jobs marked failed. The generator step passed; individual results follow. This is a real CI failure, with test setup issues and one timeout separated below.

| OS / Python | Contract suite | v2 suite | Cause |
| --- | --- | --- | --- |
| [Windows 3.10](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317541) | 7 tests, 1 error | Not reached | `powershell.exe -NoProfile -NonInteractive -Command <packaged Node invocation>` timed out after the packaged 2 seconds in the `SessionStart` subtest. Other subtests passed. This may be cold PowerShell startup or a real supported-shell deadline problem; the log does not establish which. |
| [Windows 3.12](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317686) | 7/7 pass | 87 tests, 5 failures and 5 errors | Temporary-root short-path alias `RUNNER~1` versus `runneradmin`; the v2 step does not reach the stale idempotence assertion cleanly. |
| [Ubuntu 3.10](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317667) | 7/7 pass | 87 tests, 2 failures | Stale `first["changed"]` assertion in two inherited test classes. |
| [Ubuntu 3.12](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317664) | 7/7 pass | 87 tests, 2 failures | Same stale assertion. |
| [macOS 3.10](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317753) | 7/7 pass | 87 tests, 7 failures and 5 errors | `/var` versus `/private/var` fixture paths (ten cases), plus two stale assertions. |
| [macOS 3.12](https://github.com/Mullans/skills/actions/runs/36266231221/job/108471317677) | 7/7 pass | 87 tests, 7 failures and 5 errors | Same fixture path and assertion problems. |

The test edits should address the deterministic v2 failures; this report records no CI rerun of those edits. The Windows 3.10 PowerShell timeout needs an independent rerun or targeted timing investigation with the packaged deadline preserved.

PyYAML is absent from this Python 3.14 environment (`ModuleNotFoundError: No module named 'yaml'`), so the separate metadata validator was not run. This does not affect the runtime checks above.

## Installation and source comparison

- Before testing, no Mullans marketplace or plugin was registered/installed in Mac Codex. The repo's `.agents/plugins/marketplace.json` is named `mullans` and points at `./plugins/mullans-productivity`. The source Codex and Claude manifests both say `0.6.1`.
- Registered this repository with `codex plugin marketplace add /Users/seanmullan/Documents/ChatGPT/Skills`, then installed with `codex plugin add mullans-productivity@mullans`. Codex reports `installed, enabled`, version `0.6.1`, from this checkout. Installed root: `/Users/seanmullan/.codex/plugins/cache/mullans/mullans-productivity/0.6.1`; data root: `/Users/seanmullan/.codex/plugins/data/mullans-productivity-mullans`.
- Source and installed SHA-256 hashes match: Codex manifest `aacc453ddf806e01ac495310136a8f0ebd774474dc1df069cbf6ad227daaff89`; `hooks/codex.json` `7e4f1212a436c739ea7042f65f6ed31371c95a045988d34c5bc8d4daa3757cdb`; `hooks/claude.json` `61ec32635862e8f52ffc42afef0ae93435f5967391e91827cae418d168801c15`; `bin/session-learning-hook.js` `e89c641377f52786e64f29e3455297421ed9e9b6ad0d08442dfc5836642230a7`. Installed Codex hooks use the fixed Node invocation and packaged two-second timeout.
- The local Codex manifest version remains `0.6.1`, while `origin/main` locally points at a separate 0.6.2 release. No release/cachebuster version was edited; this installation tests the `dev` checkout only. Claude Code plugin installation was unavailable.

## Live host trials

Disposable project: `/private/tmp/session-learning-macos-gl7b7ih2`. It contains a valid active `lesson.generated-files.001`, derived retrieval catalog and pointer, and `src/generated/api.py`; it is separate from the user's real lesson stores. Fresh `codex exec --json -C <project> --skip-git-repo-check` sessions used the installed plugin. No project files were modified by the trials.

| Host / event | Result and evidence |
| --- | --- |
| Codex CLI `UserPromptSubmit`, before trust | **Skipped then.** Fresh thread `01a0df43-149e-77f0-9f49-91f091a03d37` had a matching prompt, but the model reported no hook context. Installed hooks had not been reviewed/trusted. This is consistent with Codex's documented trust gate; it is not evidence of a launcher failure. |
| Codex CLI `UserPromptSubmit`, after persisted trust | **Verified.** Fresh thread `01a0df68-589c-7430-b6ea-5ee6e4ee1ed9` ran without a bypass. Its saved transcript `~/.codex/sessions/2026/09/26/rollout-2026-09-26T15-29-12-01a0df68-589c-7430-b6ea-5ee6e4ee1ed9.jsonl` contains the `lesson.generated-files.001` developer context at line 11, before the first tool call. |
| Codex CLI `PreToolUse`, after persisted trust | **Verified.** Fresh thread `01a0df67-81a8-7f43-b720-b4644f450365` ran without a bypass, with fixture trigger `src/generated/api.py` absent from the prompt. The transcript `~/.codex/sessions/2026/09/26/rollout-2026-09-26T15-28-17-01a0df67-81a8-7f43-b720-b4644f450365.jsonl` contains the lesson developer context at line 29 immediately after `rtk head -n 1 src/generated/api.py`. The observed CLI tool name was `exec`, with nested `/bin/zsh -lc`; the hook runner shell itself was not exposed. |
| Codex CLI `UserPromptSubmit`, one-off trust bypass | **Verified for this invocation.** Fresh thread `01a0df43-cd7d-7942-be82-6f0410b39700` used the documented `--dangerously-bypass-hook-trust` flag after source/hash review. Its saved model-input transcript at `~/.codex/sessions/2026/09/26/rollout-2026-09-26T14-49-17-01a0df43-cd7d-7942-be82-6f0410b39700.jsonl` contains a developer message, `Relevant session lessons: - [project:lesson.generated-files.001] Update the schema and regenerate clients...`. This is direct model-context evidence, stronger than the agent's response. A later run verified the ordinary trusted flow. |
| Codex CLI `PreToolUse`, one-off trust bypass | **Verified for this invocation.** In a fresh thread `01a0df45-90dd-73f3-a01d-42ea82013410`, the fixture trigger was `src/generated/api.py`, absent from the user prompt. The CLI called its shell tool to list files and then `rtk head -n 1 src/generated/api.py`. The saved transcript at `~/.codex/sessions/2026/09/26/rollout-2026-09-26T14-51-13-01a0df45-90dd-73f3-a01d-42ea82013410.jsonl` has the same lesson developer message immediately after that targeted tool call (line 29). This isolates retrieval to the tool event. The observed tool name in the CLI transcript is `exec`; the nested command ran via `/bin/zsh -lc`. The hook runner's own shell was not exposed. |
| Codex CLI `SessionStart` / `SessionEnd` | **No launch error observed in the fresh CLI trials; lifecycle result otherwise not directly verified.** Empty output/exit 0 is not proof of engine execution. The plugin data directory acquired `python-launcher.txt` during live use, proving launcher/Python discovery occurred at least once, but it does not isolate which lifecycle event did so. |
| Codex desktop app, all four events | **Partial observation only.** After the user trusted hooks, this pre-existing chat received a developer context message for project lesson `lesson.skill-runtime-boundary.001` after a tool call. That shows dynamic context appeared in the desktop conversation; there was no fresh desktop chat with an isolated fixture to assign the exact event or validate all four events. Desktop runtime PATH was not independently captured. |
| Claude Code, all four events | **Not tested live.** Claude desktop is installed, but Claude Code CLI and installed `mullans-skills` plugin were not found. The contract suite tests Claude's packaged exec form only. |

The live CLI's normal and bypassed runs used the same installed handler. The packaged Codex command is `node -e "require(process.env.PLUGIN_ROOT+'/bin/session-learning-hook.js').main(process.argv.slice(1))" -- --host codex`; it uses the `PLUGIN_ROOT` supplied by the host. No hook stderr, nonzero hook exit, or timeout was observed in the successful trusted CLI runs. Codex's JSONL output did not expose raw `hookSpecificOutput.additionalContext`; its model-input developer message is the direct delivery evidence available here.

## Remaining release blockers and next steps

1. Run an isolated fresh desktop chat against the disposable fixture if desktop acceptance is required beyond the observed dynamic lesson in this chat. Codex CLI retrieval is now verified with persisted trust for both events.
2. Exercise Claude Code after it is available and the plugin is installed/trusted there. Claude desktop alone does not supply that host test.
3. Rerun the six-job CI matrix after sharing the local test edits. Investigate the Windows 3.10 PowerShell `SessionStart` timeout separately; avoid claiming a pass for the packaged two-second deadline from a longer diagnostic timeout.
4. Rerun the saved behavioral evaluations with a current file inventory. Do not replace their hash or weaken the assertion merely to green the full suite.
5. Reconcile `dev` manifest version 0.6.1 with the 0.6.2 release before distribution. This local installation is not proof that existing 0.6.2 users receive the patch.

This report and `tests/session-learning/test_session_learning_v2.py` (canonical temporary fixture roots and corrected idempotence expectation) are being published together on `dev` at the user's request. No launcher implementation files were changed. Keep this report and the temporary handoff file until the cross-platform investigation is confirmed complete.
