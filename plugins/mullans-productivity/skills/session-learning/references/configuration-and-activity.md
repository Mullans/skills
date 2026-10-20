# Configuration and Activity

## Configure

Run `configure --root <project>` to inspect effective settings, their sources, errors, and hook requirements. Installation scope does not determine configuration scope.

Precedence after built-in defaults:

1. Personal defaults: `~/.agents/session-learning/config.json`.
2. Shared project settings: `<project>/.session-learning/config.json`.
3. Individual overrides: `<project>/.session-learning/config.local.json`.

Use `configure --drafting on|off` for individual project consent; user-wide drafting consent is unsupported. Use `configure --audit on|off`, optionally `--scope user`, for activity auditing. The helper preserves unrelated settings and excludes individual overrides through Git's local `info/exclude`; remove tracked overrides from tracking before enrollment.

Run `configure` on each machine. Copied overrides do not grant capture consent. Keep `configuration_owner` if editing booleans after enrollment; inspection explains disabled capture.

Hooks require installed/enabled host configuration, Node.js 22+, and Python 3.10+. A standalone skill or successful helper call does not establish hook delivery. Inspect host setup when unavailable; enable hooks only when requested. Retrieval is advisory. Use `audit` for engine-recorded errors; inspect host launch errors for failures before the engine starts.

## Inspect activity

Run `activity --root <project>` for emission counts, dispositions, backlog, live sessions, and coverage. Page lesson identities with `--lesson-page`; use `--data-dir <host-data>` to select another host. Otherwise the helper uses active plugin data or personal staging. Aggregates retain 90 calendar days.

Auditing defaults on independently of retrieval/drafting and stores counts and authority-qualified IDs only. Emissions do not prove host receipt, application, or helpfulness; characters are not tokens. Missing hosts/boundaries, interrupted sessions, or write failures mean unknown coverage, not zero activity. Live counts are provisional. Use evidence-backed [reflection.md](reflection.md), not counts alone, to assess guidance.
