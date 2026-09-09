# Skills and instruction wiring

## Discover before adding

Inspect repository skill metadata and the active environment's advertised capabilities. Personal or managed skill overlap may be reported from available metadata; do not recursively scan home directories or remove skills as part of repository setup. Similar names are not proof of equivalent behavior. Read the relevant bodies before concluding that two skills duplicate each other.

Prefer an existing skill that performs the needed recurring task without changing repository standards. A missing skill merits creation or installation only when its benefit is concrete. Inspect proposed third-party instructions and dependencies before adopting them. Use a skill creation/installation capability if available, otherwise create the standard `SKILL.md` package directly. Runtime-specific frontmatter belongs only where supported.

Keep setup and daily work separate: this setup skill configures repositories; the installed workflow note guides normal work. A pointer used during coding should reach that note, not trigger another installation pass. Avoid installing a second efficiency skill when a plain conditional reference meets the need.

## Resolve the actual client

Honor the current environment's supported discovery paths. If supporting another client, check its current official documentation or local help before writing an adapter. `SKILL.md` with name/description is shared; discovery locations and invocation controls are client-specific. Do not hardcode version-specific context budgets or assume every client follows the same paths.

Codex repository skills commonly use `.agents/skills/<name>/SKILL.md`; this environment's skill-creator may direct personal installation to `$CODEX_HOME/skills`. Claude Code repository skills use `.claude/skills/<name>/SKILL.md`. These are starting points for verification, not a reason to create every directory in every repository.

For several clients, use the existing canonical source and a small relative-path adapter if supported. Preserve the same purpose/description; explicitly resolve relative resources from the canonical skill directory. Avoid symlink requirements for portability. Do not install a personal and repository registration of the same skill just to improve discoverability. A maintained source copy outside discovery paths is different from an active duplicate installation.

## Wire once, in the effective scope

Identify effective instructions, including parent instructions, overrides, nested scope, and existing imports. Add a brief conditional pointer where it will actually load. An ignored `AGENTS.md` under an active override is not successful wiring. Preserve the existing instruction architecture; do not add `@AGENTS.md` to `CLAUDE.md` if that duplicates guidance, creates a cycle, or imports unrelated instructions.

Example shared-file addition, adapted to the repository's real note path:

```markdown
<!-- agent-efficiency-setup:begin -->
For long or tool-heavy tasks, read [agent efficiency](docs/agent-efficiency.md) for bounded inspection and output handling under this repository's existing requirements.
<!-- agent-efficiency-setup:end -->
```

Markdown links are navigational instructions, not guaranteed automatic imports. Verify the client's actual discovery when possible; otherwise report "files and pointers validated; client discovery not exercised." Inspect formatting and hooks for hidden directories too. Leave model defaults, safeguards, and global client settings unchanged unless separately requested.

Official references for runtime checks:

- [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
