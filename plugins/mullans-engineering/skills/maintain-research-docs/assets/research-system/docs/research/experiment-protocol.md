# Research experiment protocol

Use the simplest method that answers the question. Project instructions own
authorization, participation readiness and required acceptance. Operation-specific
tools own execution and restoration; project coordination procedures own shared
resources.

## Hypothesis

State the hypothesis and observations that would support or contradict it. Reuse
applicable [maintained findings](catalog/README.md) within their stated scope.

Before building the experiment, establish required setup, available capabilities,
human actions, observations and start/stop conditions. Resolve prerequisites that
would prevent execution. Keep uncertainties the experiment is intended to
investigate as questions to observe.

Run each iteration to its prepared endpoint and assess afterward. Stop when the
hypothesis is supported or contradicted within scope. If unresolved, explain the
uncertainty and what evidence would settle it.

## Observation and automation

Prepare the executable sequence before the run. Automate supported actions, reads
and transitions; delegate observations or actions without suitable automation.
Routine agent intervention should not be part of a running experiment. Reserve
collaboration for recovery or a live step that cannot reasonably be automated or
human-driven, such as interpreting an unfamiliar active data format.

### Recording boundaries

Start on the agreed supported trigger, collect available data without judging its
scientific correctness, and save captured data on the stop trigger or when
acquisition cannot continue. Acquisition readiness belongs to the recorder;
unexpected values and gaps belong to later analysis, not capture gates.

Use native events, explicit user controls or other supported triggers. Where an
experiment display is used, show relevant instructions, acknowledged recorder
state and exact start/stop conditions. Do not imply that queued preparation is
acknowledged readiness.

## Preparation and checks

Before external-state changes, establish the target, necessary backup and
restoration method through existing tooling. Reference its journal rather than
duplicating it. Action-specific protections must not gate unrelated recording.
Declare generated outputs through the project's [artifact workflow](../local-artifacts.md).

Use existing documentation and evidence to assess apparatus. Add a focused check
only for a consequential unresolved concern in changed or suspect behavior.
Unchanged tools do not need repeated verification for every experiment.

## Evidence interpretation

Separate observations, interpretations and hypotheses. Assess unexpected values,
read gaps, partial captures and human reports after the run. Keep data available
for assessment; retain only selected useful outputs before normal artifact
cleanup. Synthetic checks establish apparatus behavior, not the studied system.

Use maintained references within scope. Reopen original evidence for additional
detail, a contradiction or a specific support concern.

## Human participation

The researcher owns execution and cleanup unless the user assigns a supervisor.
Submitting a request or placing it in a queue appoints no execution owner.

Before requesting participation, provide the complete manual sequence: where to
begin, what to do, what to observe and how collection starts and stops. Follow
project readiness requirements. Keep instructions accessible in the experiment's
chosen interface.

## Error assessment and recovery

Preserve usable setup while assessing an error. If it prevents reliable
observation or continuation, explain the failure and next useful action.
Otherwise recover through the owning tool and continue from a valid state.

Before repeating a mutating action, determine whether it already took full or
partial effect. Continue independent observations where useful; display or
unrelated source gaps should not stop a healthy passive writer. Keep restoration
independent of recording success.

## Closeout and lasting records

Update the owning investigation with the question, actual method, observations,
limits, evidence and next decision. A short note suffices for quick work; use
relevant [template](../../experiments/TEMPLATE.md) fields as needed. Record
consequential adaptations and repeated setup costs, not another command-by-command
narrative.

Close writers, restore agreed temporary changes through their owning tools,
verify the applicable final state and release shared resources. Do not treat
routine data produced by the studied system as disposable setup unless its
restoration was agreed. Retain selected evidence under the artifact workflow and
meet project acceptance requirements before closing the experiment.

Promote supported reusable findings under the
[reference policy](../wiki.md#research-promotion).
