# Session-learning tool-trigger filtering — 2026-10-05

## Resume here

Investigate whether configuring which tools trigger Session Learning hooks can reduce overhead without losing useful lesson delivery. The user noticed frequent `PreToolUse` entries in logs and requested a future investigation requiring research and experimentation before implementation. No hook configuration or runtime changes are authorized by this handoff.

**Next action:** Verify host matcher behavior and observed tool names, establish a current baseline, then experiment with narrower triggering and cheaper no-match handling in an isolated fixture. Use `temp_{os}_live_fixture` for temporary live validation.

Build on the [earlier performance handoff](session-learning-hook-performance-20260928.md), which contains historical Windows timing samples and usefulness questions. Revalidate those samples against the current version rather than treating them as current measurements.

## Current observations

- The repository and installed `mullans-productivity` 0.8.0 Codex hook configuration both use `Bash|PowerShell|apply_patch|Read|Glob|Grep|Edit|Write` for `PreToolUse`. This filters tool calls before launching the hook; it is not a wildcard for every tool.
- The matcher is unanchored. Determine whether substring matches affect observed coverage before recommending exact-name anchors.
- A matching invocation launches the Node bootstrap, probes a Python interpreter, then invokes the retrieval engine. Lesson relevance and delivery cooldown are evaluated afterward. Suppressing repeated lesson injection does not avoid process startup.
- The engine uses tool input text and extracted paths for relevance. Shell reads and writes may share a tool name, so tool-name filtering alone cannot distinguish them.
- Official [hook documentation](https://learn.chatgpt.com/docs/hooks) documents regex tool-name matchers and hooks on nested code-mode tool calls. Verify supported names and behavior on the installed host; do not infer actual invocation counts from visible log entries alone.

## Research and experiments

1. Map actual hook payload tool names to shell, patch, read/search, MCP, and nested code-mode calls. Check matcher semantics, aliases, and whether log entries represent event dispatch or an executed handler.
2. Measure invocation counts, startup/probe/engine durations, no-match and cooldown outcomes, lesson-bearing rate, and total added wall-clock delay. Account for batching and concurrency. Avoid retaining raw commands, prompts, or transcripts.
3. Compare the current matcher with exact-name anchors and narrower tool sets. Test whether removing dedicated read/search triggers misses path-specific lessons or guardrails that were not delivered on prompt submission.
4. Evaluate lightweight early exits before Python startup, including retrieval-disabled and no-applicable-lesson cases. Establish how catalog changes and project/local configuration remain visible before considering caching.
5. Replay representative positive and negative cases, including shell reads/writes and nested calls, to compare overhead and lesson coverage. Record cross-host differences where relevant.

## Decision criteria

Produce a recommendation supported by measured overhead savings and documented coverage tradeoffs. Distinguish handler executions from lesson injections, and historical process-time estimates from measured wall-clock delay. Identify any missed guardrails and how they would be preserved. Treat narrower matchers, early exits, and caching as hypotheses, not selected implementations.

## Implementation references

- [Codex hook configuration](../../plugins/mullans-productivity/hooks/codex.json)
- [Node bootstrap](../../plugins/mullans-productivity/bin/session-learning-hook.js)
- [Retrieval engine](../../plugins/mullans-productivity/skills/session-learning/scripts/session_learning.py), especially `_handle_hook_event_unlocked`

Keep investigation records and development-only fixtures outside the distributable skill directory. Follow up with the user on the findings before implementing an optimization.
