---
name: research-setup
description: Set up an empty research workspace or organize an existing project while preserving its working conventions.
---

# Research setup

Use when explicitly requested. Establish the workspace and its documentation
routing. Optimize for one user working with agents, short context loads and
continuity across sessions. The installed experiment protocol owns proportionate
research setup, checks, automation and recording; keep those rules out of routing
documents and templates.

Use the four sibling skills together: `research-setup` establishes the system,
`research-handoff` preserves continuation, `research-promotion` elevates supported
current-session findings, and `maintain-research-docs` owns wiki policy, reference
formats, catalogs and the numbered maintenance procedure. The installer
preflights all four resources; do not repeat that check before invoking it.
Standard paths below belong to this reusable system.

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
select work to resume, and consult `docs/handoffs/README.md` when preserving work for a later session. Explain that durable
knowledge goes into records even when transient artifacts are later discarded.

Research handoff supplies the canonical local lifecycle and continuation formats. For `next-handoff.md`, use its
[index asset](../research-handoff/assets/next-handoff.md) and
[format reference](../research-handoff/references/formats.md).
Keep an existing equivalent format when adopting a project, and leave a new index
empty until there is real work to resume. Do not fabricate completed work or verification.

Generated files contain local links and concrete tool contracts, so they remain
readable outside the skill installation. Preserve existing handoff lifecycle
decisions rather than replacing them merely to match a new-project default.

Create `docs/research/README.md` from the [research index](assets/findings.md),
even before there are findings. Install the maintenance skill's packaged system:

```sh
python <research-setup-skill>/scripts/install_research_pipeline.py --root <project-root>
```

Resolve the skill path from this installation; run with the project's approved
Python execution prefix. The installer preflights all four skills and assets,
creates only missing files and preserves existing bytes. It installs:

- `docs/handoffs/README.md`: handoff lifecycle, supplied by `research-handoff`.
- `docs/research/experiment-protocol.md`: research decisions, evidence interpretation,
  readiness, execution and closeout.
- `docs/wiki.md`: placement, splitting and promotion policy.
- `docs/research/reference-template.md`: reference and unit formats.
- `docs/research/catalog/README.md`: evidence retrieval and applicability review.
- `docs/research/catalog/maintenance.md`: the numbered audit/approved-batch procedure.
- Catalog configuration, subject registry and maintenance registry in that catalog.
- Catalog, maintenance, Markdown and link tools in `scripts/workspace/`.

Read the topic owners as needed. Keep the project guide as routing and placement
policy; lifecycle, execution, unit schema and reference maintenance belong to their
linked owners. Operating guidance contains current policy, with historical evidence
in owning records. Verify preserved information and inbound links when consolidating.
For adoption, compare preserved files with the bundled owners; retain meaningful
constraints and record equivalent owner paths in `docs/README.md`. Configure
catalog roots/exclusions and classify existing reference pages honestly. Never
replace accepted baselines or create fictional reviews to clear diagnostics.
Report unresolved adoption decisions together. Installer `--check` verifies
presence only; it does not establish policy or tool compatibility.

Record project-specific paths, executable commands and prerequisites, tool/input
contracts, and deliberate threshold overrides in their project owners. Keep
the standard defaults unless an explicit project decision changes them.

If Git is used, merge suitable ignores for `local/`, machine-specific config,
environments, dependencies, and builds while preserving authored files. Check for
already tracked material that ignores will not remove. Git initialization is a
choice, not a prerequisite; follow project instructions for local staging and commits; setup does not authorize
remote publication.

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
Keep coordination in that procedure and preparation, readiness and cleanup in the
experiment protocol; route to these owners instead of copying their steps.
Run its tests on temporary fixtures; setup does not acquire live resource claims.

The core already establishes research policy, formats, catalogs and maintenance.
Add subject pages when supported findings qualify through `research-promotion`;
new research is recorded in experiments first. Use `research-handoff` for
continuation and `maintain-research-docs` for organizational review.

Done: applicable additions have clear owners; absent optional components remain
absent. Missing prerequisites are distinguished from verified setup.

## 4. Verify and report

Check local links and template-relative paths, including links that will change
when templates become records. Check that generated instructions refer to project
files, not this skill installation or unavailable helpers. For new installations
or changed configuration, run checks of affected setup capabilities; avoid live-system experiments. Reuse
applicable checks on an unchanged setup. State what was actually verified and what remains unavailable.

For a new core installation, run the installed catalog `check`, maintenance
`audit`, and link checker from the root. On adoption or rerun, select only checks
needed for the changed infrastructure. Read tool `--help` when arguments are
unclear. Python standard library is required; Git is required for baseline measurements and approved
maintenance commits. Audit exit 1 means measured review is required; exit 2
means incomplete/error. Report missing runtimes or adoption gaps instead of
claiming the complete research system is verified. Do not invent scientific
findings or approvals to demonstrate setup.

Report what was reused, added or repaired, the root README, and unresolved
prerequisites. An already-sufficient setup may finish without file changes. Setup
is complete once the core research system is usable or remaining prerequisites
are explicitly reported as incomplete. An empty project needs no first investigation
or product-language environment; its research tools still require Python. Do not begin substantive research merely to demonstrate
the setup.
