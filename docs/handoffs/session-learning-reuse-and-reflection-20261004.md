# Session-learning reuse and reflection evaluation — 2026-10-04

## Resume here

Investigate whether captured lessons reach the agent and improve later repository work. The 0.8.0 behavioral comparison captured seeded learning moments consistently, but did not establish improved reuse or a benefit from reflection. The user requested this handoff to preserve those findings for future work.

**Next action:** Trace accepted lessons through future-request retrieval, then design native repository tasks that exercise the normal discovery and verification routes. Start from the [validation report](../session-learning/validation-0.8.0.md) and [compact behavioral results](../../tests/session-learning/extension_behavioral_results_0_8_0.json). This investigation is ready for implementation review when it distinguishes delivery, application, and verification failures; proposes a reproducible evaluation; and identifies any concrete runtime changes supported by the evidence.

Repository starting point: local commit `d86a003`, session-learning 0.8.0. This handoff records follow-up work; it does not authorize changes to capture methodology or remote publication.

## Findings and their limits

- **Capture was more consistent than subsequent usefulness.** Both capture arms produced 21 seeded-relevant drafts and no routine-work drafts. Exact reuse path scores were 5/24 for baseline, 6/24 for drafting, 3/24 for reflection, and 5/24 for combined. These bounded decision scores do not establish a performance gain or complete procedural correctness.
- **Some accepted active lessons were not emitted for differently phrased requests.** For example, a `client response change` trigger did not match a generated-client field-addition request. This raises a question about trigger quality and retrieval coverage. It does not establish that all reuse failures share that cause.
- **The reuse environment omitted normal retrieval routes.** Native file discovery, manual lesson-index lookup, and pre-tool retrieval were unavailable. The comparison therefore understates the routes available during repository work. The 96 trajectories also shared eight-project cohort contexts, leaving three independent cohort repetitions per arm; they were decision tasks rather than executed code changes.
- **Compaction exposed verification gaps.** Some observations stayed deferred because supporting verification was unavailable in the fresh review context. Deferral may be appropriate under the evidence gates; investigation should distinguish necessary caution from avoidable loss of traceable evidence.
- **Reflection preserved bytes on small healthy stores.** Repeated reflection produced no maintenance churn. Transactional consolidation is covered by structural tests, but this behavioral set does not demonstrate that consolidation improves guidance or subsequent work.

## Follow-up work

1. **Trace retrieval before changing capture.** For accepted lessons, inspect scope, triggers, future request wording, eligible retrieval surfaces, and actual emissions. Compare request-only matching with normal path discovery and pre-tool retrieval. Record separately whether guidance was eligible, emitted, consulted, applied, and useful. Finish with representative missed-delivery cases and a supported explanation or an explicit unresolved question for each.
2. **Evaluate native repository tasks.** Extend the fixed fixtures to execute meaningful work and verification while allowing ordinary file discovery, index lookup, and pre-tool context. Retain corrections, verified successful workflows, non-lessons, unresolved evidence, long sessions, and compaction. Specify the fixture set, repetitions, arms, model/tool setup, and scoring before running. Measure capture precision/recall, review burden, context and drafting overhead, task success, repeated corrections, and successful reuse. Report variability and the retrieval route used; keep cohort and individual-task costs separate.
3. **Examine review continuity after compaction.** Identify which sanitized source references and verification results remain available to retrospective review. Test whether sufficient traceable evidence can survive context loss without retaining conversation logs or weakening promotion gates. Finish by separating appropriately deferred drafts from drafts whose supporting evidence could have been preserved safely.
4. **Test reflection where maintenance is warranted.** Add stores with compatible same-authority redundancy, contradictions, unresolved candidates, and guidance carrying necessary exceptions or conflict history. Include unsupported synthesis and already healthy stores as controls. Assess semantic quality, preserved provenance, coverage, later reuse, and repeat-run churn. Fewer active records alone is not a success criterion.

Use development fixtures under `temp_{os}_live_fixture` and repository-approved `rtk uv` commands. Keep durable evaluation tools and reports outside distributable skills. The existing eight-fixture, three-repetition, four-arm comparison is a screening baseline; agree on the native-task evaluation budget before treating it as a replacement benchmark.

## Boundaries to preserve

Keep automatic drafts machine-local and outside retrieval. Preserve explicit retrospective acceptance, verification gates, conditional exposure with drafting off by default, privacy, authority boundaries, and hash-guarded transactions. Reflection should draw on existing sanitized evidence; activity counts can identify questions but cannot establish helpfulness or justify new learning rules by themselves.

Changes to capture criteria, reminder policy, configuration, or skill implementation should be concrete proposals for separate approval. Diagnose trigger and review quality before expanding capture. Report cross-authority contradictions and preserve same-authority provenance, exceptions, and conflict history during consolidation.

## Relevant files

- [Validation report](../session-learning/validation-0.8.0.md): findings, measurements, reproduction commands, and coverage limits. The behavioral runtime was frozen before three final safeguards; its hash and the final runtime hash remain distinct in the results.
- [Compact results](../../tests/session-learning/extension_behavioral_results_0_8_0.json) and [fixed fixtures](../../tests/session-learning/extension_behavioral_fixtures.json): durable evaluation evidence. Raw ignored logs are supplementary, not prerequisites for resuming.
- [Cohort harness](../../tests/session-learning/run_extension_cohorts.py) and [individual tool-use harness](../../tests/session-learning/run_extension_behavioral.py): current evaluation entry points. Native tool-use support alone does not establish that a fixture executes a representative repository task.
- [Runtime skill](../../plugins/mullans-productivity/skills/session-learning/SKILL.md) and [architecture](../session-learning/architecture.md): current workflow and invariants.
- [Hook performance handoff](session-learning-hook-performance-20260928.md): related investigation of invocation cost and rule usefulness; coordinate measurement definitions when the work overlaps.
