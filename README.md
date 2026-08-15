# Mullans Skills

These are the agent skills I use across different projects, so everything is set up to be used with either ChatGPT or `npx skills`.

## Available skills

| Category | Plugin | Skill | Purpose |
| --- | --- | --- | --- |
| Productivity | `mullans-productivity` | `brainstorm` | Turn a free-form idea dump into a structured, resumable brainstorm document without inventing content. |
| Productivity | `mullans-productivity` | `mark2word` | Convert styled Markdown and YAML-frontmatter documents into Microsoft Word `.docx` files. |

## Install through the ChatGPT/Codex marketplace

Add this repository as a marketplace, then install the Productivity bundle:

```bash
codex plugin marketplace add Mullans/skills
codex plugin add mullans-productivity@mullans
```

Start a new ChatGPT or Codex conversation after installation. In the ChatGPT desktop app, you can also open the Plugins Directory, choose **Mullans Skills**, and install **Mullans Productivity**.

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

## Repository structure

```text
.agents/plugins/marketplace.json              # ChatGPT/Codex marketplace catalog
.claude-plugin/plugin.json                    # npx skills compatibility index
plugins/
└── mullans-productivity/                     # One installable category bundle
    ├── .codex-plugin/plugin.json
    └── skills/
        ├── brainstorm/                       # Canonical skill files
        └── mark2word/
```

The compatibility manifest and Codex manifest are intentionally separate: they have different schemas and distribution scopes. Both point to the same skill folder.

## Add another skill

For an existing category:

1. Add the canonical skill folder under `plugins/<category-plugin>/skills/<skill-name>/`.
2. Add the skill path to the `skills` array in `.claude-plugin/plugin.json`.
3. Update the category plugin metadata and README catalog.
4. Bump the category plugin and compatibility manifest versions.
5. Validate both distribution paths before publishing.

For a new category, create a new `mullans-<category>` plugin and add one entry to `.agents/plugins/marketplace.json`. Keep each skill in exactly one category plugin.

Use semantic versions: patch for compatible corrections, minor for new skills, and major for breaking workflow changes.

## Validate locally

Check what `npx skills` discovers without installing anything:

```bash
npx skills@latest add . --list
```
