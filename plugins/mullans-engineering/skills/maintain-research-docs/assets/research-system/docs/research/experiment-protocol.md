# Research experiment protocol

This document owns method selection, proportionate preparation and checks,
evidence interpretation, human briefing, adaptation and closeout. Use the
[catalog](catalog/README.md) for retrieval and [wiki policy](../wiki.md) for
reference promotion. Project instructions own authorization and goal acceptance;
project tool and resource procedures own execution, backup and restoration.

## Research decision

Choose setup, checks, automation and documentation to support the intended
observation and the conclusion it needs to justify. Judge preparation by what it
lets us learn, including feasibility, reuse and human effort. Brief events can
justify substantial apparatus; simple observations need simple effort.

Identify what to learn and why the next action could help. Consult relevant prior
evidence through the catalog and reuse sufficient methods or saved observations.
Let questions develop during exploration. Routine offline analysis needs no
written plan or decision form; existing chat or investigation context can establish
purpose.

Plan in more detail when consequential changes, dependent steps, expensive setup
or precise measurements require it. Specify the conditions, controls, sequence
and stopping bounds needed to execute and interpret that work. Compare alternatives
when the choice materially affects effort or evidence quality.

Stop investigating a question when evidence answers the practical need within
stated limits. Pursue mechanisms or additional repeatability when remaining
uncertainty affects the intended use or the user requests deeper work. Continue
other required work within the authorized goal; retain any required human
acceptance decision.

## Observation and automation

Select human observation, screenshots, manual captures, scripts or coordinated
recording according to persistence, timing, precision and repeatability. Manual
observation is an ordinary method and needs no exception justification.

Use local triggers, timers or recording when chat latency or manual timing would
miss the required event or undermine the claim. Define the clock-start event and
timing accuracy for timed claims. A rough wait can support a rough observation;
an exact interval needs an appropriate timing mechanism.

Automate the parts that need reliable timing or benefit from convenience. Reuse
existing automation when helpful; missing convenience automation does not block a
feasible manual experiment. Build instrumentation for a named missing observation.
Use coordinators, transition detection and capture acknowledgements where the
measurement requires them, following their owning tool procedures.

## Preparation and checks

Simple experiments and unchanged known procedures need no additional tests by
default. Add a check for a concrete likely failure in changed or suspect behavior
that could prevent the trial, silently invalidate its intended conclusion, or
compromise safe operation or restoration. General software fallibility is
insufficient justification.

Use the smallest sufficient check: a relevant diff, syntax check, focused dry run
or inspection of the first output may suffice. The experiment itself can check
apparatus when failure is inexpensive and detectable. A code edit does not
automatically require new tests. Stop checking once the concern is resolved;
repeat or broaden checks only for new evidence or a material change.

Treat changed fingerprints as prompts to inspect applicability, not proof of a
blocker. Keep unrelated shared-tool hardening with its owning effort. Count test
authoring, repairs, repeated execution, documentation and user waiting as
preparation cost. If preparation expands, identify the necessary observation each
addition enables and simplify or defer work that does not help obtain it.

Apply authorization, ownership, target identity, backup and restoration safeguards
to the operations that require them, through their project owners. Those safeguards
do not justify unrelated validation. Select product and release checks through
their own development procedures.

## Evidence interpretation

Distinguish observed, derived and hypothesized claims. Record environment,
source/build/input identities, method revisions and conditions needed to establish
applicability or reproducibility. Include exact hashes when conclusions depend on
exact bytes. Retain selection criteria, tolerances, deviations and run identities
where they affect interpretation.

Accept preliminary observations with their limits. A reported change can be useful
evidence before a controlled comparison establishes causality. Strengthen the method
when a stronger conclusion is needed. Separate unavailable coverage from a negative
result; fixtures, static analysis and live observations establish different scopes.

Review decisive source spans before relying on consequential claims. Copies and
summaries share one evidence lineage. Reconcile contradictions by source quality
and applicable conditions, not recency alone. Check relevant claims in a source
with a known error while retaining independently supported evidence.

Treat predictions as hypotheses. Assess unexpected observations as possible effects,
supporting evidence, counterevidence or apparatus defects. Unexpected does not imply
erroneous; an error does not invalidate every observation.

## Readiness and execution

Complete agent-controlled offline preparation before requesting participation;
finish required live preflight after applicable readiness authorization and before
the measured action. Before each phase, explain its question, necessary
user-controlled conditions, actions, required observations and relevant stop
conditions. Give enough context to perform them: where to find a target, how to
recognize it, what to look for and what to report. Disclose uncertainties.

Distinguish requirements from suggestions and predictions. Specify timing,
position or other controls only where the observation depends on them. Give an
ordered sequence when order matters and an overview of later phases when they
affect setup or user commitment. Treat an undisclosed necessary prerequisite as
an agent preparation error; assess existing observations for their supported scope.

Follow project permission and readiness rules before external or time-sensitive
work; an absent response is not approval. Verify only the setup and instruments
required for the chosen observation. Setup or documentation maintenance does not
authorize live experiments.

Adapt routine parameters within the authorized experiment without restarting
planning or readiness approval. Preserve attribution when changing a condition;
explain consequential changes before user action. Obtain authorization for a new
objective, new external mutation or materially different risk. Follow project
readiness rules when starting a later experiment.

## Failure assessment and recovery

Assess what failed and which actions or conclusions it affects. Stop the affected
work; stop more broadly when safe operation, restoration or subsequent evidence
integrity is compromised. Preserve useful partial observations and continue
independent work when feasible. Defer unrelated tool defects.

Preserve usable expensive setup and retained output. Assess the failed condition
before retrying, resetting, restoring or releasing resources. Inspect only the
identities, state, coverage or writer health relevant to recovery. Prefer bounded
same-session repair and revalidate affected prerequisites before resuming. Explain
why existing state cannot support continuation before requesting a reset.

Before repeating a missed capture, inspect retained evidence and identify an
observation improvement or justified repeatability question. A missing internal
explanation alone does not justify another run.

## Closeout and lasting records

Update the owning investigation rather than creating another checkpoint for each
adjustment. A short question/action/result/next-step note can suffice for quick
work; use relevant parts of the [template](../../experiments/TEMPLATE.md) for fuller
investigations. Proportionality needs no classification or justification form.

Write details before acting when execution, interpretation or safe restoration
depends on them. Record useful results afterward with relevant conditions,
evidence locations, limits and next action. Retain commands, source pinpoints and
identities where needed to reproduce or assess findings. Identify originals and
derivatives, retrieval limits and transient data that cannot be regenerated.
Record significant delays or tooling problems when they offer an actionable
correction; routine closeout needs no cost ledger or token accounting.

Complete applicable cleanup, writer closure and final-state verification through
their owning procedures. Record remaining work and the supported answer without
making unrelated tool acceptance a research completion gate. Put reusable operating
steps in procedural owners and keep trial history in the investigation. Promote
qualifying findings under wiki policy. Use [handoff lifecycle](../handoffs/README.md)
only for eligible cross-session continuation, not same-session acceptance waits.
