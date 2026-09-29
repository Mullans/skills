---
name: research-setup
description: Set up an empty research workspace or organize an existing project while preserving its working conventions.
---

# Research setup

Use when explicitly requested. Establish the workspace; research execution and
publishing are separate tasks. Optimize for one user working with agents, short
context loads, and continuity across sessions.

## 1. Identify the starting point

Read applicable project instructions. Inspect root names, relevant manifests,
existing navigation and current work; use bounded reads rather than ingesting
datasets, logs, or the entire repository. Identify whether the project is empty
or already in use. Preserve unrelated changes and established working commands.

For existing material, read [adoption.md](references/adoption.md) before edits.
Ask only for decisions that prevent useful setup. An empty project may have an
undecided purpose, no workstreams, no inputs, and no chosen language. Record those
honestly; do not invent a research plan to fill the scaffold.

Done: the target root and setup mode are identified; existing instructions and
working paths are accounted for; proposed migrations are separated from changes
that can proceed.

## 2. Establish the core

Adapt [project-guide.md](assets/project-guide.md) into `docs/README.md`: it owns
placement, navigation, expansion triggers, and record conventions. Preserve useful
rules while adapting paths and removing authoring notes. Adapt
[agent-instructions.md](assets/agent-instructions.md) into `AGENTS.md`; merge with
existing instructions instead of replacing them.

Create or reconcile:

- `README.md`: purpose/scope, human usage, links to docs and current work.
- `AGENTS.md`, `docs/README.md`, and `next-handoff.md`.
- `src/`, `scripts/`, `tests/`, `local/` (empty directories are fine; Git need not
  preserve them using placeholder files).
- `experiments/TEMPLATE.md` from [investigation.md](assets/investigation.md).
- `docs/handoffs/TEMPLATE.md` from the handoff skill's
  [snapshot template](../research-handoff/assets/handoff.md).

The root README should explain: add working inputs under `local/`, ask the agent
to begin a bounded investigation or implementation task, use `next-handoff.md` to
select work to resume, and request a handoff before stopping. Explain that durable
knowledge goes into records even when transient artifacts are later discarded.

Research handoff owns continuation formatting. For `next-handoff.md`, use its
[index asset](../research-handoff/assets/next-handoff.md) and
[format reference](../research-handoff/references/formats.md).
Keep an existing equivalent format when adopting a project, and leave a new index
empty until there is real work to resume. Do not fabricate completed work or verification.

Distribute these two skills together for setup's template resources. The handoff
skill operates independently. If those resources are unavailable during setup,
preserve existing handoff files and report the missing templates rather than
silently maintaining another default schema. Generated project files must remain
usable without either skill installed.

If Git is used, merge suitable ignores for `local/`, machine-specific config,
environments, dependencies, and builds while preserving authored files. Check for
already tracked material that ignores will not remove. Git initialization is a
choice, not a prerequisite; setup does not stage, commit, push, or publish.

Done: every core role has a path or preserved equivalent; templates and their
pointers resolve from generated locations; root navigation reaches them without
requiring either skill.

## 3. Add only applicable components

Use the expansion table in the project guide. Agents may create these standard
components when their triggers apply. New top-level categories or migrations of
established material require a concrete proposal and user agreement.

When languages, environments, or distributables are relevant, read
[components.md](references/components.md). Choose conventional component layouts,
preserving working ones. Install tools or dependencies only for an identified
setup need within the user's authorization; a language-free scaffold is complete
without speculative installations.

When concurrent work can interfere with a resource, read
[resource checkout](references/resource-checkout.md). Preserve an existing protocol;
for a new one, install the bundled generic helper, disposable tests, and adapted
procedure only after defining resource scopes and one shared authority path.
Run its tests on temporary fixtures; setup does not acquire live resource claims.

Finding conventions have a stable home in the generated project guide from setup
onward. When creating the first research subject, adapt the
[subject index](assets/findings.md) into `docs/research/README.md` and link it from
navigation. Its pointer to those conventions replaces copying or moving the
taxonomy into templates or subject pages.

Done: applicable additions have clear owners; absent optional components remain
absent. Missing prerequisites are distinguished from verified setup.

## 4. Verify and report

Check local links and template-relative paths, including links that will change
when templates become records. Check that generated instructions refer to project
files, not this skill installation or unavailable helpers. For configured code,
run appropriate existing safe setup checks; avoid live-system experiments. State
what was actually verified and what remains unavailable.

Report what was reused, added or repaired, the root README, and unresolved
prerequisites. An already-sufficient setup may finish without file changes. Setup
is complete once the workspace can receive new material and support future work. An empty project needs no first investigation
or installed environment. Do not begin substantive research merely to demonstrate
the setup.

When maintaining or releasing these skill packages, use
[acceptance checks](references/acceptance.md); they are not routine setup work.
