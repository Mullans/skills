# Windows startup diagnosis — 2026-09-26

## Authorized remote execution

The user explicitly authorized one manually triggered Windows-only diagnostic
job, capped at five minutes, with no OS/Python matrix or automatic triggers.
[Run 36271659968](https://github.com/Mullans/skills/actions/runs/36271659968)
tested commit `70ada1040584e12b88ddb497a8a5426012dc7f10`.
The one Windows job ran from 21:04:13 to 21:04:42 UTC (29 seconds); the full-suite
job was skipped. No second execution was requested. Duration is elapsed time,
not an assertion about billing.

Environment: GitHub Windows Server 2025 runner image `20260922.246.2`, Python
3.12.10, Node 22.23.2. The diagnostic copied the plugin into a temporary fixture,
instrumented that copy, and executed the literal packaged command with a
ten-second observation window. This did not change the shipped two-second limit.

## Reproduction and localization

The first Windows PowerShell SessionStart invocation completed successfully in
**2,226 ms**, reproducing an overrun of the shipped deadline. Output matched the
expected payload/arguments, exit status was zero, and stderr was empty.

| Phase | Milliseconds after process launch |
| --- | ---: |
| First marker inside the Node launcher module | 1,953 |
| Input read started/completed | 1,986 / 1,986 |
| Python probe started/completed | 1,988 / 2,036 |
| Probe engine started/completed | 2,037 / 2,082 |
| Process/output collection complete | 2,226 |

The next PowerShell SessionStart invocation completed in **310 ms**. PowerShell
real lesson retrieval completed in **415–422 ms**; cmd.exe real retrieval in
**246–248 ms**; PowerShell 7 real retrieval in **564 ms**. All 18 diagnostic
invocations completed with verified output. No invocation exhausted ten seconds.

This establishes a first-invocation startup overrun in the PowerShell launch path
on this runner, rather than a persistent hang or invalid command. Most time was
spent before the launcher entered; its Python probe took 48 ms and probe engine
45 ms. The trace does not split the pre-entry period into PowerShell initialization,
OS/security scanning, Node startup, or initial module loading, so attributing all
1,953 ms to a particular Windows subsystem would exceed the evidence.

The association with SessionStart was test order: it was the first command for
that shell. A host could encounter cold startup on another event too. This also
does not retrospectively prove the cause of the original 0.6.2 desktop failures.

## Correction

Codex's outer timeout is five seconds for SessionStart, UserPromptSubmit, and
PreToolUse, with three seconds for SessionEnd to respect its documented host cap.
Claude's shell-free exec adapter retains two seconds. The Node launcher's 1.4-second
work budget and 250-ms interpreter probes remain unchanged.

This separates process-startup allowance from useful-work allowance. The 2.226s
observed invocation fits the new outer deadline; the five-second choice provides
startup margin rather than asserting an exact universal upper bound. No sleep or
shell warm-up was inserted into acceptance tests. Their deadlines still come from
the shipped configuration, and real output remains required. The engine-failure
test now exercises both hosts to retain bounded, non-blocking behavior.

The launcher already starts Python without a shell. Adding an explicit cmd wrapper
inside a PowerShell hook would not remove the host's outer PowerShell startup, and
changing the user's host shell is outside this fix. A shell-free Codex hook form,
if supported by a future host contract, could remove that startup boundary.

## Verification limits

Local validation passed all seven launch-contract tests and all 89 v2 tests;
generated configuration and whitespace checks also passed. The broader v2 run
exposed a separate Windows no-op bug: activation normalized an existing AGENTS.md
from CRLF to LF and reported a change. Activation now preserves the existing
pointer bytes, with explicit LF/CRLF regression cases. No platform-dependent
assertion was weakened to accommodate that rewrite.

The approved remote run diagnosed the old deadline. It did not run the complete
suite or test the later timeout configuration; no additional remote run is
authorized by that approval. Local acceptance tests can verify the new config and
engine behavior, but a fresh-runner acceptance result remains pending. Updated
installed Windows desktop delivery, live Claude Code delivery, historical
evaluation evidence, and release/cache version reconciliation remain separate
outstanding checks. Automatic CI remains disabled.
