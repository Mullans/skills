# Mullans Skills

These are the agent skills I use across different projects, packaged for ChatGPT/Codex, Claude Code, and standalone `npx skills` installation.

## Available skills

| Category | Plugin | Skill | Purpose |
| --- | --- | --- | --- |
| Productivity | `mullans-productivity` | `brainstorm` | Turn a free-form idea dump into a structured, resumable brainstorm document without inventing content. |
| Productivity | `mullans-productivity` | `mark2word` | Convert styled Markdown and YAML-frontmatter documents into Microsoft Word `.docx` files. |
| Productivity | `mullans-productivity` | `session-learning` | Preserve evidence-backed project lessons and retrieve only relevant active guidance during later work. |
| Engineering | `mullans-engineering` | `agent-efficiency-setup` | Audit or improve repository agent efficiency while preserving existing engineering standards and workflows. |
| Engineering | `mullans-engineering` | `make-it-so` | Execute an approved implementation plan through validated completion. |
| Engineering | `mullans-engineering` | `research-setup` | Establish or organize a research workspace while preserving existing conventions. |
| Engineering | `mullans-engineering` | `research-handoff` | Preserve research or implementation work for a later session. |
| Engineering | `mullans-engineering` | `research-promotion` | Promote supported current-session findings into maintained references at research milestones. |
| Engineering | `mullans-engineering` | `maintain-research-docs` | Review reference organization and apply approved maintenance batches. |

## Install through the ChatGPT/Codex marketplace

Add this repository as a marketplace, then install the bundle you need:

```bash
codex plugin marketplace add Mullans/skills
codex plugin add mullans-productivity@mullans
codex plugin add mullans-engineering@mullans
```

Start a new ChatGPT or Codex conversation after installation. In the ChatGPT desktop app, you can also open the Plugins Directory, choose **Mullans Skills**, and install **Mullans Productivity**.

## Install through the Claude Code marketplace

Add this repository as a marketplace, then install the bundle you need:

```text
/plugin marketplace add Mullans/skills
/plugin install mullans-skills@mullans
/plugin install mullans-engineering@mullans
```

## Install with `npx skills`

Browse and choose from the skills in this repository:

```bash
npx skills@latest add mullans/skills
```

Install one skill that has no sibling dependency:

```bash
npx skills@latest add mullans/skills --skill <skill>
```

The four research skills form one pipeline. For a standalone installation, install **all four in the same target**:

```bash
npx skills@latest add mullans/skills --skill research-setup
npx skills@latest add mullans/skills --skill research-handoff
npx skills@latest add mullans/skills --skill research-promotion
npx skills@latest add mullans/skills --skill maintain-research-docs
```

Select the same agent and skills directory for all four commands. Setup uses the sibling handoff resources and installs the maintenance skill's standard wiki, reference formats, catalog configuration and Python tools. The `mullans-engineering` marketplace plugin includes all four.

Research lifecycle: `research-setup` establishes the workspace;
`research-handoff` preserves open work between sessions; `research-promotion`
codifies supported findings from the current session; `maintain-research-docs`
reviews maintained references. Promotion is a milestone step, not a prerequisite
for handoff or a recurring experiment-backlog audit.

> [!IMPORTANT]
> Choose either the marketplace plugin or the standalone `npx skills` installation for a given Codex environment. Installing the same skill through both channels can lead to duplicate skills with the same name.

## Specific Skill Notes

### Session Learning

The `session-learning` skill comes with four hooks that need to be enabled/trusted for the skill to work best: 

* `UserPromptSubmit`: Fires whenever the user submits a prompt and injects active lessons whose triggers or topics clearly match that prompt.
* `PreToolUse`: Fires before supported shell, search, read, and edit tools and injects lessons matching the pending operation, command, or file path without blocking or modifying the tool call.
* `SessionStart`: Fires on startup, resume, clear, and post-compaction—and on Claude forks—to initialize, restore, or clear retrieval state and restore relevant lessons when earlier context may have disappeared.
* `SessionEnd`: Fires when the main session ends and removes that session’s transient cooldown/relevance state while pruning stale state files.

The `session-learning` retrospective is manual. It can preserve repository guidance in `.session-learning`, keep project-specific personal guidance in a hashed store under `~/.agents/learning/projects/`, and optionally mine bounded Codex history for verified recovery patterns. Historical mining is always read-only until the explicit retrospective accepts a finding. Version 0.8.0 adds optional machine-local draft capture, explicit semantic reflection, and local activity reports. Canonical lesson/evidence schemas are unchanged.

Patch release 0.8.1 adds evidence-scoped diagnosis and prioritized recommendations for enforcement, navigation, tool cost, and information access. Migration now follows supported older lesson schemas rather than writing-release age; compatible current-schema lessons retain their original writing version and require no migration after a skill release bump.

Patch release 0.8.2 scopes maintenance safeguards to the proposed transaction and keeps superseded or retired lessons out of routine indexes and search. Historical records and their evidence remain available through explicit historical review or search --include-history; replacement guidance may cite newer evidence that corrects earlier findings. No schema migration is required.

Drafting defaults off. Run `python <skill-root>/scripts/session_learning.py configure --root <project> --drafting on` to enroll just this user/machine/project. This creates `.session-learning/config.local.json`, excludes it using Git's local `info/exclude`, and reports exact editable paths and effective settings. Subsequent manual edits are read at later hook events. The command works with global or project skill installation; mutable settings never live in installation files. User defaults and committed project settings cannot enable capture. Use `configure` without setting arguments for read-only inspection, or `--audit on|off` to control activity measurement independently.

Enabled hooks emit one compact drafting pointer at initialization, first-prompt fallback, context restoration, or an enable transition. Full capture instructions load only through the gated `draft-context` helper at a meaningful learning moment. There are no periodic reminders. Disabling emits one revocation notice and stops future automatic instructions and saves. Disabled projects receive no drafting instructions or save attempts. Automatic exposure requires functioning plugin hooks; standalone skill installation alone does not install them.

Drafts stay in hashed machine-local staging and never enter retrieval or repository state. An explicit retrospective reviews pending/deferred observations, preserves verification gaps, and accepts lessons through a recoverable receipt-backed handoff. Reflection reviews existing canonical evidence through stable, bounded snapshots and hash-guarded maintenance, preserving provenance, exceptions, conflict history, and historical usage. Request `session-learning` reflection to consolidate guidance; request activity to inspect emission/capture/review counts and coverage. Counts measure engine emissions and characters, not exact tokens or proven helpfulness. Aggregate activity retains 90 days and does not store prompts, tool arguments, lesson text, raw project paths, or conversation logs.

Version 0.7.0 uses only `.session-learning` for project state. Move earlier stores using the two-sentence instructions in [the skill](plugins/mullans-productivity/skills/session-learning/SKILL.md#retrospective). Personal project guidance stays in its separate hashed home store; writing it may require host permission approval.

Automatic retrieval requires Node.js 22+ on the host application's PATH and Python 3.10+ on Windows, macOS, and Linux. Both host adapters use the same JavaScript launcher, which starts Python directly without a shell. Claude uses executable-plus-arguments hooks; Codex uses a fixed command that reads the plugin path inside Node rather than expanding it in shell code. If Python is unavailable, the launcher returns normally and the project-local index remains the fallback. If Node itself cannot start, the host reports a launch failure; the launcher cannot suppress a failure that occurs before it runs. A terminal finding Node does not prove that an already-running desktop app has the same PATH; restart the host after changing runtime installations.

You can adjust automatic retrieval for one project in `.session-learning/config.json`, or set personal defaults for all projects in `~/.agents/session-learning/config.json`. Individual overrides in `.session-learning/config.local.json` take priority over both. Include only settings you want to change.

```json
{
  "schema_version": 1,
  "retrieval_enabled": true,
  "cooldown_user_prompts": 5,
  "max_lessons_per_event": 3,
  "max_context_characters": 4000,
  "python_path": "C:\\Path\\To\\Python\\python.exe"
}
```

- `retrieval_enabled` turns automatic lesson retrieval on or off.
- `cooldown_user_prompts` controls how many later prompts must occur before the same lesson can be shown again.
- `max_lessons_per_event` limits how many lessons can be added at one time.
- `max_context_characters` limits the combined length of lessons added at one time.
- `drafting_enabled` defaults false and requires individual project enrollment; edit it in the excluded project override after enrollment.
- `activity_audit_enabled` defaults true; disabling it does not change retrieval or drafting decisions.
- `python_path` optionally gives the full path to a Python 3.10+ executable. The launcher tries the project setting, then the personal setting, then platform discovery: `py -3`, `python3`, and `python` on Windows; `python3` and `python` on macOS/Linux. It reads the project setting relative to the event's `cwd`, regardless of the launcher's own working directory.

The configured Python path must point directly to an executable, not contain command options. Discovery and engine execution are bounded within the hook deadline. If no usable Python installation is found within that budget, automatic retrieval remains off and Session Learning displays one short notice at session start; the project-local lesson index remains available to the agent. Prefer a personal `python_path` for machine-specific locations rather than committing a Windows or Mac path into shared project settings.

Cross-platform launch checks and the remaining host-installation acceptance steps are documented in [the hook investigation](docs/session-learning/windows-hook-investigation.md). A passing unit test or a host's “Completed” badge alone does not prove that lesson context was delivered.

Our Codex hooks allow up to five seconds for a hook process, including shell startup (three seconds for SessionEnd, its host limit). Claude's direct-exec hooks retain a two-second limit. The launcher still bounds Python discovery and engine work to 1.4 seconds after input is read; the additional Codex allowance covers measured Windows startup overhead, not extra retrieval work. The [Windows timing report](docs/session-learning/windows-startup-diagnostic.md) records the reproduced overrun and verification limits.

## Development Notes

Deferred work is listed in [the current-work handoff index](next-handoff.md).

### Repository structure

```text
.agents/plugins/marketplace.json              # ChatGPT/Codex marketplace catalog
.claude-plugin/marketplace.json               # Claude Code marketplace catalog
plugins/
├── mullans-productivity/                     # Productivity skills bundle
    ├── .codex-plugin/plugin.json
    ├── .claude-plugin/plugin.json
    ├── bin/                                  # Codex and Claude hook launchers
    ├── hooks/
    │   ├── codex.json
    │   └── claude.json
    └── skills/
        ├── brainstorm/                       # Canonical skill files
        ├── mark2word/
        └── session-learning/
└── mullans-engineering/                      # Engineering skills bundle
    ├── .codex-plugin/plugin.json
    ├── .claude-plugin/plugin.json
    └── skills/
        ├── agent-efficiency-setup/
        ├── make-it-so/
        ├── research-setup/
        ├── research-handoff/
        ├── research-promotion/
        └── maintain-research-docs/
tools/session-learning/                       # Maintainer-only hook generator
```

### Add another skill

For an existing category:

1. Add the canonical skill folder under `plugins/<category-plugin>/skills/<skill-name>/`.
2. Add the skill path to the `skills` array in `plugins/<category-plugin>/.claude-plugin/plugin.json`.
3. Update the category plugin metadata and README catalog.
4. Bump the category plugin and compatibility manifest versions.
5. Validate both distribution paths before publishing.

For a new category, create a new `mullans-<category>` plugin and add entries to both marketplace catalogs. Keep each skill in exactly one category plugin.

Use semantic versions: patch for compatible corrections, minor for new skills, and major for breaking workflow changes.

### Validate locally

Check what `npx skills` discovers without installing anything:

```bash
npx skills@latest add . --list
```

Development tests and maintainer architecture records live under repository-level `tests/` and `docs/` and are not part of the distributable skill folder. Use the [research skills acceptance checks](docs/research-skills-acceptance.md) when maintaining or releasing those skills.
