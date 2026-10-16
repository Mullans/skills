# Configuration and Activity

Use `configure --root <project>` to inspect effective values, their source files, configuration errors, and hook availability requirements. Installation scope does not determine configuration scope.

- Personal defaults: `~/.agents/session-learning/config.json`.
- Shared project settings: `<project>/.session-learning/config.json`.
- Individual project overrides: `<project>/.session-learning/config.local.json`.

Ordinary settings apply in that order after built-in defaults. `configure --drafting on|off` changes the current project's individual override. `configure --audit on|off` changes the individual project audit setting; add `--scope user` for audit defaults. User-wide drafting consent is unsupported. Explicit configuration preserves unrelated settings, creates missing files only when writing, and excludes individual project configuration through Git's local `info/exclude`. Tracked individual configuration must be removed from tracking before enrollment.

Project configuration also enrolls a machine-owned opaque identity inside the project's hashed personal staging area. `configuration_owner` matches that enrollment. This prevents copying or accidentally committing an individual override from opting other users into capture. After enrollment, users can edit the booleans directly; keep the owner field. To enroll a different machine, run `configure` there. Without matching enrollment, drafting stays disabled and inspection explains why.

Automatic exposure requires installed, enabled, functioning host hooks and their Node/Python runtimes. A standalone skill folder does not install lifecycle hooks. Inspect host hook configuration when unavailable; neither an installation path nor a successful helper proves hook delivery. Do not silently enable hooks during configuration.

## Local activity

Use `activity --root <project>` to inspect counts, lesson emissions, draft dispositions/reasons, backlog age, live sessions, coverage limits, and the 90-calendar-day aggregate retention window. Lesson identities are ranked by emission count and paged in groups of 20 with `--lesson-page`; inspect more pages when relevant. `--data-dir <host-data>` selects a host's plugin data explicitly; otherwise the helper uses the active plugin environment or personal staging activity directory. Reports also include staging helper counts. Inspect another host separately when its data directory is unavailable. Interrupted or pruned transient sessions can leave incomplete coverage. Long-lived sessions flush counters at UTC day changes.

Auditing defaults on and is independent of retrieval/drafting. It collects only counts and authority-qualified lesson IDs. Context/lesson counts describe engine emissions, not host receipt, application, or helpfulness; character counts are not token counts. Successful measurements create no working-context notices. Missing hosts, missed session boundaries, and write failures leave unknown coverage rather than inferred zero activity.

Reflection can use these summaries with sanitized lesson evidence to investigate low-impact drafting, repeated duplicate capture, repeated violations, and maintenance churn. Counts alone establish no cause or effectiveness. Changes to capture methodology, reminder policy, configuration, or installed skill implementation are proposals requiring separate approval. Existing grounded lesson maintenance remains authorized by explicit reflection.
