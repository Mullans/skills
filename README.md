# Mullans Skills

These are the agent skills I use across different projects, packaged for ChatGPT/Codex, Claude Code, and standalone `npx skills` installation.

## Available skills

| Category | Plugin | Skill | Purpose |
| --- | --- | --- | --- |
| Productivity | `mullans-productivity` | `brainstorm` | Turn a free-form idea dump into a structured, resumable brainstorm document without inventing content. |
| Productivity | `mullans-productivity` | `mark2word` | Convert styled Markdown and YAML-frontmatter documents into Microsoft Word `.docx` files. |
| Productivity | `mullans-productivity` | `session-learning` | Preserve evidence-backed project lessons and retrieve only relevant active guidance during later work. |

## Install through the ChatGPT/Codex marketplace

Add this repository as a marketplace, then install the Productivity bundle:

```bash
codex plugin marketplace add Mullans/skills
codex plugin add mullans-productivity@mullans
```

Start a new ChatGPT or Codex conversation after installation. In the ChatGPT desktop app, you can also open the Plugins Directory, choose **Mullans Skills**, and install **Mullans Productivity**.

## Install through the Claude Code marketplace

Add this repository as a marketplace, then install the shared skills bundle:

```text
/plugin marketplace add Mullans/skills
/plugin install mullans-skills@mullans
```

## Install with `npx skills`

Browse and choose from the skills in this repository:

```bash
npx skills@latest add mullans/skills
```

Install only one skill:

```bash
npx skills@latest add mullans/skills --skill <skill>
```

> [!IMPORTANT]
> Choose either the marketplace plugin or the standalone `npx skills` installation for a given Codex environment. Installing the same skill through both channels can lead to duplicate skills with the same name.

## Specific Skill Notes

### Session Learning

The `session-learning` skill comes with four hooks that need to be enabled/trusted for the skill to work best: 

* `UserPromptSubmit`: Fires whenever the user submits a prompt and injects active lessons whose triggers or topics clearly match that prompt.
* `PreToolUse`: Fires before supported shell, search, read, and edit tools and injects lessons matching the pending operation, command, or file path without blocking or modifying the tool call.
* `SessionStart`: Fires on startup, resume, clear, and post-compaction—and on Claude forks—to initialize, restore, or clear retrieval state and restore relevant lessons when earlier context may have disappeared.
* `SessionEnd`: Fires when the main session ends and removes that session’s transient cooldown/relevance state while pruning stale state files.

The `session-learning` retrospective is manual. Its automatic read path uses advisory hooks and an optional Python 3 runtime; if Python is unavailable, the hooks fail open and the project-local index remains the fallback. 

You can adjust automatic retrieval for one project in `.agents/learning/config.json`, or set personal defaults for all projects in `~/.agents/session-learning/config.json`. Project settings take priority, and you only need to include settings you want to change.

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
- `python_path` optionally gives the full path to a particular Python 3 executable; when omitted or unavailable, Session Learning tries `py -3`, `python3`, and `python` automatically.

The configured Python path must point directly to an executable, not contain command options. If no usable Python 3 installation can be found, your work continues normally, automatic retrieval remains off, and Session Learning displays one short notice at session start; the project-local lesson index remains available to the agent.

## Development Notes

### Repository structure

```text
.agents/plugins/marketplace.json              # ChatGPT/Codex marketplace catalog
.claude-plugin/marketplace.json               # Claude Code marketplace catalog
plugins/
└── mullans-productivity/                     # One installable category bundle
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

Development tests and maintainer architecture records live under repository-level `tests/` and `docs/` and are not part of the distributable skill folder.
