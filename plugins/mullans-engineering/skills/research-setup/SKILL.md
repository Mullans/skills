---
name: research-setup
description: Set up an empty research workspace or organize an existing project while preserving its working conventions.
---

# Research setup

Use when explicitly requested. Establish usable research entry points, document
owners and supporting tools. Preserve existing human-authored rules and working
conventions. Setup does not begin an investigation or authorize live operations.

## 1. Inspect and reuse

Identify the target, requested scope, applicable instructions, existing owners and
working commands. Inspect relevant paths and manifests, not the whole corpus.
For an existing project, read [adoption](references/adoption.md).

Reuse sufficient structure. An empty project need not have a chosen product
language, workstreams, findings or a first experiment. Create source and test
directories when there is something to put in them.

## 2. Establish the owners

Use the following roles without duplicating their content:

| Role | Destination or source |
| --- | --- |
| Purpose and human entry points | Root `README.md` |
| Stable agent routing and project constraints | Merge [agent instructions](assets/agent-instructions.md) into `AGENTS.md` |
| Documentation navigation | Adapt the [documentation index](assets/project-guide.md) into `docs/README.md` |
| Investigation fields | Adapt the [template](assets/investigation.md) into `experiments/TEMPLATE.md` |
| Maintained subject navigation | Adapt the [research index](assets/findings.md) into `docs/research/README.md` |
| Continuation formats | Reuse `research-handoff`'s [index](../research-handoff/assets/next-handoff.md), [snapshot](../research-handoff/assets/handoff.md) and [format reference](../research-handoff/references/formats.md) |
| Reference policy, formats, retrieval and maintenance tools | The packaged research pipeline below |
| Placement rules, if needed | A concise local workspace owner, such as `docs/workspace.md` |

Indexes contain links and short descriptions; procedures contain normal operating
steps and configuration; references contain supported facts and essential limits;
implementation owners contain technical contracts and diagnostics; templates
contain fields. Experiments preserve observations, interpretation and provenance.
Promote reusable methods into maintained code or tool guides.

Generated links must resolve from their project destinations. Include only
existing or newly established owners, preserve equivalent paths, and remove setup
comments. Keep a new continuation index empty until there is work to resume.
Root navigation should reach the topic owners without copying their instructions.

## 3. Install and adapt

For a new full research system, run with the project's Python execution prefix:

```sh
python <research-setup-skill>/scripts/install_research_pipeline.py --root <project-root>
```

The installer preflights the four existing research skills, installs missing
pipeline files and preserves existing bytes. It supplies the protocol, reference
policy/formats, catalog and maintenance configuration/tools, handoff lifecycle,
and portable artifact support. Its `--check` checks presence, not compatibility.
Do not invoke the full installer during adoption merely to fill unrelated absent
roles; it has no selective-installation mode.

Keep project policy and configured values with their local owners. Configure
actual tool paths when adopting equivalents; a prose mapping alone does not
reconfigure a tool. Preserve accepted baselines and existing lifecycle systems.
Shared packaged defaults have their own owners; propose discrepancies rather than
silently replacing adopted project policy.

Read only the applicable setup references:

| Situation | Guidance |
| --- | --- |
| Existing structure needs adaptation or migration | [Adoption](references/adoption.md) |
| Code, a language environment, specialist tools or distribution is needed | [Components](references/components.md) |
| Artifact storage or a relevant producer needs integration | [Artifact workflow adoption](references/artifact-storage.md) |
| Concurrent work can interfere with a concrete shared resource | [Resource checkout](references/resource-checkout.md) |

Use one artifact authority. The installer preserves a detected existing artifact
system for adaptation; use `--artifact-mode existing` for equivalents elsewhere.
Add project/tool indexes, external-reference catalogs and recovery guides when
there is useful material to organize. Add a roadmap only when priorities,
dependencies or deliberate deferrals need a persistent owner; it is not a feature
inventory or current-work tracker.

Keep dependency versions in manifests and lockfiles. Record necessary execution
context and specialist-tool adoption in the toolchain owner. Merge appropriate
ignores when Git is used, preserving tracked work. New dependencies or external
actions remain subject to the project's authorization.

`research-promotion` promotes supported reusable knowledge and methods; `maintain-research-docs`
owns organizational maintenance; `research-handoff` owns continuation.
`research-audit` is optional for a requested capability or efficiency review,
not a fifth installer dependency or a setup verification step.

## 4. Check and report

| Change | Appropriate check |
| --- | --- |
| Navigation or template | Local links, including links resolved from the eventual record destination |
| New full pipeline | Installed catalog `check`, maintenance `audit` and link checker |
| Changed configuration or integration | The affected command or disposable fixture |
| Artifact producer or cleanup integration | Relevant output, failure and closeout cases in temporary storage |
| Existing unchanged component | Reuse sufficient checks; do not revalidate merely because setup ran |

Audit exit 1 means organizational review is identified; exit 2 means the audit is
incomplete. Preserve those findings without making full legacy onboarding a setup
prerequisite. The helper tools require Python; Git is needed for committed-baseline
measurements and maintenance commits. Do not fabricate research to exercise them.

Report what was reused, added or repaired, the usable entry points, checks and
specific remaining gaps. Distinguish a usable requested setup from a partial one.
An already-sufficient project can finish with no edits. Do not run live experiments
to demonstrate setup or claim unintegrated components are covered.
