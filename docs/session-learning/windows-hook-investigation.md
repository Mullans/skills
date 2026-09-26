# Cross-platform hook investigation (2026-09-26)

## Correction to the first diagnosis

The installed 0.6.2 plugin and repository both shipped
`call "%PLUGIN_ROOT%\bin\session-learning-hook.cmd" --host codex`.
It fails when evaluated by PowerShell, but that reproduction does not prove the
desktop app evaluated its hooks in PowerShell. The initial investigation wrongly
treated the interactive tool shell as evidence of the hook runner's shell.

Codex's current upstream command runner defaults to COMSPEC/cmd.exe on Windows,
using /C and a raw outer-quoted command string. It defaults to SHELL (or /bin/sh)
with -lc on Unix. An explicit shell configuration can change the runner. The
installed CLI is 0.158.0-alpha.2.1; upstream main is not proof of every detail of
that build. The exact original desktop failure remains unconfirmed without an
actual hook execution trace. Neither the initial cmd-only test nor the subsequent
PowerShell-only fix established the host contract adequately.

Sources:
- [Codex command runner](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/engine/command_runner.rs)
- [Codex hook configuration](https://learn.chatgpt.com/docs/hooks)
- [Claude exec and shell forms](https://code.claude.com/docs/en/hooks#exec-form-and-shell-form)

## What made this implementation fragile

- Three independent implementations of Python discovery in shell, PowerShell, and
  JavaScript, plus a Windows batch wrapper. The POSIX copy parsed JSON using sed,
  used process cwd rather than payload cwd, and did not consistently fall back
  from an unusable project interpreter to the personal interpreter.
- Configuration syntax tied to one shell without establishing the host's shell.
- Tests supplied their own launcher command or cmd wrapper rather than exercising
  every shipped definition at the host boundary.
- A supposed host-acceptance test only asserted that Codex's debug prompt renderer
  echoed its input. It never asserted hook execution or retrieved context.
- Unbounded runtime probes inside a two-second host deadline.
- Zero exit status used as a health signal even though retrieval intentionally
  returns success on failure. Pre-engine failures cannot reach engine diagnostics.
- Development checkout, marketplace checkout, and installed cache treated as if
  changing one necessarily updated the others.

These are implementation and verification problems, not an inherent limitation of
skills or a requirement imposed by lesson retrieval.

## Replacement

Both hosts now use one standard-library JavaScript launcher and the existing
Python engine. Automatic retrieval requires Node.js 22+ on the host PATH and
Python 3.10+. This makes Node an explicit Codex prerequisite too; native Codex or
Claude installation alone does not promise Node is on PATH.

Claude uses its documented executable-plus-arguments form. Codex uses the same
fixed command for both command and commandWindows:

```text
node -e "require(process.env.PLUGIN_ROOT+'/bin/session-learning-hook.js').main(process.argv.slice(1))" -- --host codex
```

The command text contains no substituted filesystem path or shell environment
expansion. Node reads the root as data, loads the bundled launcher, and starts
Python with an argument array and shell:false. The shell, batch, and PowerShell
launchers are removed rather than maintained as divergent fallbacks.

The launcher parses JSON normally, uses the payload's cwd for project settings,
tries personal configuration after an unusable project setting, uses platform
appropriate discovery, forces UTF-8 at the Python boundary, and bounds probes and
engine execution. It does not forward partial output from a crashed/timed-out
engine. A missing Node binary remains a host launch error; a missing Python
runtime produces a once-only startup warning when the launcher can run.

## Verification and its limits

The new contract suite reads installed-layout hook JSON and executes those exact
commands. Windows coverage includes cmd.exe with Codex's upstream raw quoting
shape, Windows PowerShell, and PowerShell 7. Native Unix runners exercise available
sh/bash/zsh login shells. Claude exec-form placeholder substitution is simulated
as argument data, not shell source.

Checks include all four events, intact UTF-8 payload and arguments, real lesson
context for both retrieval events and both hosts, paths with spaces/Unicode/shell
metacharacters, launch cwd distinct from event cwd, absent Python, invalid cache
content, project-to-personal interpreter fallback, discovery/cache reuse, invalid
data directory, engine crash, and engine timeout. Positive retrieval is required
within the packaged two-second limit.

Local Windows results: all seven contract tests and all 87 v2 tests passed.
These tests establish adapter behavior, not actual desktop dispatch, trust, or
model-context consumption. The old prompt-echo test was removed rather than
presented as host verification.

The CI workflow runs the contract and v2 suites on windows-latest, ubuntu-latest,
and macos-latest with Python 3.10 and 3.12 and Node 22. It has not been run remotely
during this investigation. No native macOS or Linux result is claimed. Docker's
Linux engine is not running locally and WSL is unavailable.

## Deployment acceptance still required

The installed plugin is 0.6.2 under
`~/.codex/plugins/cache/mullans/mullans-productivity/0.6.2`. Its registered marketplace
is `~/.codex/.tmp/marketplaces/mullans`, a Git checkout of
`git@github.com:mullans/skills`, not this working tree. This checkout's Codex manifest
still says 0.6.1. Reinstalling the unchanged marketplace cannot deliver this patch.

1. Run the native CI matrix on an isolated branch containing these changes.
2. Deliver through the registered marketplace release flow with a distinct
   release/cache identity; reconcile the 0.6.1/0.6.2 discrepancy.
3. Inspect installed hook definitions and verify Node/Python availability from
   the host environment. Start a fresh chat and review/trust changed hooks.
4. Use a disposable project with a known active dynamic lesson. Verify actual
   UserPromptSubmit and PreToolUse context delivery in Codex and Claude on each
   supported OS. A Completed badge or exit 0 alone is insufficient.
5. Capture the host-selected command, shell, and stderr for any failure before
   assigning its cause. Never infer the hook shell from the tool shell.

## Historical behavioral evaluations

The separate saved behavioral-evaluation fingerprint was stale before this work.
Its recorded file inventory now also includes the retired launchers. Those old
results must not be relabeled as a fresh evaluation by replacing their hash.
The full suite's historical-evidence check remains a release limitation until
those evaluations are rerun; the new runtime tests do not claim to replace them.
