# Research experiment protocol

This document owns research decisions, evidence interpretation, experiment
readiness, execution and closeout. Use [catalog guidance](catalog/README.md) for
retrieval and [wiki policy](../wiki.md) for reference promotion. Project instructions
govern authorization and goal acceptance; a measured stopping condition does not
override a required human acceptance decision.

## Research decision

Complete this short block before further research or a user test. It also applies
to analysis performed without a live system. Use [the experiment template](../../experiments/TEMPLATE.md)
for new investigations; adapt existing records in place.

- **Decision and deliverable:** What will someone be able to do, or what choice
  will this work change? Link the roadmap gate or explicit user request.
- **Existing evidence inspected:** Cite decisive source sections and their
  applicability, including later results that supersede pending instructions.
- **Missing discriminator and expected outcomes:** State what is unknown, what
  the possible observations mean, and what action follows each. An unavailable
  or rejected observation is a coverage failure, not a negative system-behavior result.
- **Cheapest sufficient method:** Compare reuse, existing-capture analysis,
  bounded static inspection, implementation from an established contract and a
  new live observation. Explain why the selected method resolves the blocker.
- **Acceptance and stopping condition:** Name the observable completion gate and
  a bounded artifact set, code region, test sequence or analysis endpoint. State
  when to redirect and what new evidence would reopen a deferred branch.

Separate delivering a feature from explaining every internal mechanism. Continue
causal analysis when it blocks the chosen contract or the user explicitly asks
for it. When the gate is met, consolidate the result. Choose another gate only for
required unfinished work within the authorized overarching goal. Build instrumentation only for a named missing observation; fixture checks,
capture volume and test counts establish their own scope, not broader behavior.

After a capture misses its discriminator, inspect saved evidence and lifetime or
coverage limits before another run. Identify a concrete observation improvement
or change method. An identical run needs a reason such as a justified repeatability
comparison; script availability and incomplete explanation alone are insufficient.

## Evidence interpretation

Distinguish observed, derived and hypothesized claims. State relevant source or
build identity, environment, inputs and lifecycle conditions. Static inspection,
fixture checks, live observation and delivery validation establish different scopes.
Review decisive source spans; copies and summaries share one evidence lineage.
Reconcile contradictions by source quality and applicable conditions, rather than
recency alone. If an extraction contains a known-false claim, check its relevant
claims before relying on it while retaining independently supported source evidence.

Record source pinpoints, method/code revision, effective configuration, deviations
and repeated-run identity where they affect interpretation. Use hashes for exact
bytes and source versions, selection criteria or tolerances where appropriate.
Preserve originals while needed and identify analysis or redacted derivatives.

## Readiness and execution

Before user action, communicate all phase-specific prerequisites, the ordered
action sequence, expected observable outcomes, timing/transition ownership, required
confirmations, stop conditions and final-state requirements. Distinguish required
conditions from suggestions and predictions from observations. Verify prepared
inputs, target identity, instrumentation coverage and output paths within authorized
scope. Resolve missing required identity or observations before dependent actions.
Assess an unexpected setup against the requirements actually communicated; an
omitted prerequisite is a protocol defect, not user noncompliance.

Follow project-specific permission and readiness rules before starting external or
time-sensitive work. An absent response is not approval. Use the project's execution
and shared-resource owners for commands, coordination, backup and restoration;
setup or documentation maintenance does not authorize live experiments.
When measurements depend on transitions, use a coordinator and recorder
acknowledgements or document why a manual procedure supplies adequate evidence.
Stop on invalid setup, stale instrumentation or missing acknowledgements; preserve
the failed attempt and verify recovery before another run.

## Closeout and lasting records

Reconcile results, checks, limitations, current state and remaining required work
in the owning experiment or implementation record. Retain useful negative and
inconclusive results. Record source identities and artifact paths with retrieval or
regeneration limits; never promise regeneration of transient data. Keep small
shareable excerpts or regression fixtures when useful. Missing evidence must remain
visible when it limits a conclusion. Cleanup and log deletion need their own scope.

Preserve reusable error diagnosis: symptoms, cause, diagnostic method, fix and
verification. Put enduring operating steps in their procedural owner and link the
evidence record. Operating guidance and reference pages contain current policy or
supported knowledge; experiment records own trial logs, migration reports and
historical narrative. Before removing duplicate instructions, verify the governing
document retains every applicable rule. Preserve unique evidence at its owning
record and repair discovery links.

Promote qualifying findings under wiki policy and record promotion dispositions,
reviews and checks in the experiment. Follow the applicable resource procedure for
writer shutdown, final-state verification and release, retaining its evidence receipt.
Use [handoff lifecycle](../handoffs/README.md) only for eligible cross-session
continuation. Waiting for same-session acceptance stays in the owning record.
