# Session-learning hook performance — 2026-09-28

## Resume here

Evaluate whether Session Learning's `PreToolUse` hook runs too often for the useful guidance it returns. The user wants to discuss optimization in a separate conversation, including narrower tool matching or other ways to reduce time and work per call. No hook changes have been made for this investigation.

**Next action:** Establish per-invocation timing and outcome measurements for a representative Codex session, then compare narrower triggering or a cheaper no-match path. The evaluation is done when it reports invocation count, wall-time distribution and total added delay, rule-bearing rate, and useful-rule rate, while checking that important guardrails still reach the agent.

## Observations from this conversation

- The installed `mullans-productivity` 0.6.3 configuration matches `Bash|PowerShell|apply_patch|Read|Glob|Grep|Edit|Write` for `PreToolUse`, with a five-second outer timeout. It also registers `UserPromptSubmit`, `SessionStart`, and `SessionEnd` hooks. See [the hook configuration](../../plugins/mullans-productivity/hooks/codex.json).
- In the two completed work turns, the rollout recorded 47 completed shell commands and four file changes. These are **51 potentially matching operations**, not a confirmed count of hook invocations. The hook has no per-invocation success/timing log.
- Two developer-context injections appeared after tool calls. They contained three distinct lessons: skill runtime boundary, remote Git authorization, and review-wave boundaries. Plugin state confirms those three lesson IDs were delivered during the first prompt sequence; it does not record unsuccessful/no-match calls.
- The injection appeared about 451 ms and 397 ms after the corresponding tool calls were issued. These are **call-to-delivery intervals**, not isolated hook runtimes. The tool work continued afterward.
- In a separate ten-run replay of the installed hook on this machine, using a synthetic `PreToolUse` payload and disposable plugin data, each process completed successfully in 493–558 ms. One run returned a rule; the others returned no rule because of cooldown. This is a current local sample, not historical timing for the conversation's calls. The replay script and data were placed in the ignored `temp_windows_live_fixture/` directory and are not a durable project artifact.
- The runtime-boundary lesson visibly prompted classification of the bundled test as a template used by the skill. The remote-authorization lesson repeated `AGENTS.md`; the review-wave lesson had no clearly attributable effect. Thus one of three delivered lessons was clearly useful, and one of 51 potentially matching operations yielded that useful lesson. This is a small, subjective sample, not a general effectiveness rate.
- At roughly 0.5 s per invocation, 51 serial invocations would total about 25 s of process time. Batching and concurrent calls make that **not** a measured wall-clock slowdown. There is no basis to assign an actual duration to each past invocation. A [prior Windows diagnostic](../session-learning/windows-startup-diagnostic.md) observed a 2,226 ms first invocation on a CI runner under an older deadline; it does not establish a cold-start time for this conversation.

## Relevant implementation and evidence

- [Node launcher](../../plugins/mullans-productivity/bin/session-learning-hook.js): starts a process for each hook call, probes Python, and gives the engine a 1.4 s internal work budget. The outer hook timeout also covers PowerShell and Node startup.
- [Retrieval engine](../../plugins/mullans-productivity/skills/session-learning/scripts/session_learning.py): handles `UserPromptSubmit` and `PreToolUse`, loads project and local catalogs, scores lessons, suppresses recently delivered lessons, and writes delivery state. Search for `_handle_hook_event_unlocked`.
- [Windows startup diagnostic](../session-learning/windows-startup-diagnostic.md): prior launch timing and the reason for the five-second Codex timeout.
- Current installed plugin state lives under `%USERPROFILE%\.codex\plugins\data\mullans-productivity-mullans`. The current conversation's rollout is under `%USERPROFILE%\.codex\sessions\2026\09\28\` with session ID `01a0eacb-ab0b-79d1-97b3-a63409a6e080`. These are local evidence locations, not committed inputs; inspect only what is needed and avoid retaining raw transcript content.
- Repository state at handoff: `dev` commit `60ed6f9` (engineering plugin 0.2.1). Unrelated deletions of `temp_macos_investigation_report.md` and `temp_windows_investigation_instructions.md` were present and left untouched. PR [#4](https://github.com/Mullans/skills/pull/4) existed for the separate engineering-skill work; this handoff does not require changing it.

## Questions for the later discussion

1. Which tool calls can be skipped without missing context-specific guardrails? The current matcher is broad; the useful lesson in this sample was associated with skill packaging.
2. Can no-match calls return before Python startup or catalog loading, while still detecting path and command triggers reliably?
3. Should delivery avoid repeating guidance already present in `AGENTS.md`, and how should usefulness be judged beyond whether a rule was emitted?
4. What instrumentation can record durations and outcomes without storing command text, prompts, or transcripts?

Treat these as options to test, not chosen implementation work. Revalidate timing on the target host and plugin version before changing hook behavior.
