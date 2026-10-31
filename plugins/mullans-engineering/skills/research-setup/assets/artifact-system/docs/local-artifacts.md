# Local artifacts

This document owns generated-artifact lifetimes. Use the
[experiment protocol](research/experiment-protocol.md#closeout-and-lasting-records)
for evidence assessment and restoration. Run commands from the project root with
its approved Python prefix.

## Defaults

Artifacts start transient. Use one experiment identity across its tests and
sessions; session disappearance never makes evidence orphaned. Place scripts,
builds, captures, analysis, samples and rollback snapshots in that experiment's
registered workspace. Files inherit ownership regardless of how they were made.
Promote reusable code into maintained source/scripts; publish validated
distributables through the project's release workflow.

Preserve an artifact only for a succinct unresolved question, expected reuse or
unique verification capability. Expensive recreation alone is insufficient.
The helper requires recorded approval above 200 MiB; adapt that threshold to the
project. Evergreen sources have one canonical home and consumer references.
Failed captures with no evidential use retire after failure assessment and
verified writer closure. Preserve useful partial evidence and unresolved recovery.

## Normal workflow

The portable standard-library helper uses one SQLite registry under
`local/artifacts/`. Keep an established equivalent helper and authority when
adopting an existing project; never run parallel lifecycle registries over the
same files.

```sh
python scripts/workspace/artifact_workspace.py begin EXPERIMENT --session SESSION
python scripts/workspace/artifact_workspace.py run --root local/experiments/EXPERIMENT --input local/experiments/SOURCE/analysis/source.bin -- python scripts/analyze.py
```

The second command claims its declared local inputs, owns its temporary directory
and reconciles new or changed files after success or failure. It passes
`RESEARCH_ARTIFACT_ROOT`, `RESEARCH_ARTIFACT_OWNER`, `TEMP`, `TMP` and `TMPDIR`
to the child. Producers must write under the root or an explicit owned output.
This wrapper is coordination, not a filesystem sandbox; it cannot intercept an
arbitrary tool's hardcoded external paths. Adapt those destinations before use.

For separately closable tests, register a distinct `--test TEST --root PATH`
beneath the same experiment, before writing. Use category-specific test roots
where practical. The registry records experiment, test and creating session;
claims can belong to several consumers simultaneously.

After results and evidence disposition are assessed, the owning workflow runs:

```sh
python scripts/workspace/artifact_workspace.py finish --root local/experiments/EXPERIMENT --experiment --assessment "Results assessed; evidence disposition complete" --writers-closed --apply
```

Use an exact registered root. Omit `--experiment` to finish only that test. `--apply` retires its
unclaimed transient payloads and newly unclaimed payloads from closed producers.
Other experiments remain active. Without `--apply`, finish releases consumers
and reports candidates without deleting them. Closeout follows the project's
authorization requirements; a session ending or a restored snapshot is not
experiment completion.

A running or interrupted job blocks finish. `cleanup` reports unresolved job
IDs; after verifying writer closure, use `assess-job ID --writers-closed
--assessment TEXT`. This records assessment without retrying the command or
certifying recovery. Detached writers need operation-specific closure receipts.

## Preservation and shared recommendations

```sh
python scripts/workspace/artifact_workspace.py preserve PATH --reason "Canonical input used by the parser"
python scripts/workspace/artifact_workspace.py publish PATH --reason "Upcoming parser comparison"
python scripts/workspace/artifact_workspace.py pool
python scripts/workspace/artifact_workspace.py claim-pool ENTRY --root local/experiments/NEXT
```

Preservation persists until `retire ENTRY --reason TEXT`. Recommendations expire
after seven days; `renew ENTRY --reason TEXT` verifies their bytes and grants
another seven days. Active consumers continue protecting expired entries.
Claims reference immutable bytes in place; the pool adds no payload copies.
`resolve --root ROOT DIRECTORY` verifies a reused output reference, claims its
retained files and prints the canonical directory.

## Deterministic reuse

Use `run --recipe RECIPE.json --output NEW-DIRECTORY` for expensive reproducible
operations. Declare every local input with `--input`; include effective settings,
tool identities and implementation files in the recipe:

```json
{
  "operation": "pack-candidate",
  "implementation": ["scripts/pack_candidate.py", "config/tool-lock.json"],
  "settings": {"compression": 6},
  "retain": ["candidate.bin", "manifest.json"],
  "candidate": true
}
```

Pass `--verify-command` as a JSON argument array for a separate independent
verification operation. A candidate recipe requires it. Generation runs first;
every newly generated candidate receives fresh verification before reuse is
recorded. Verification failure or missing retained outputs prevents caching.
Use experiment scratch for disposable verification decodes.

A recipe hit verifies retained content, acquires input claims and writes only
`artifact.reference.json` in the new output directory. Inputs declared with `--input` resolve directory references automatically;
other downstream consumers must use `resolve` before reading them. Changed inputs, implementations, settings or verification
commands invalidate reuse. Matching in-progress recipes are refused. Recipe
metadata preserves nothing by itself; normal closeout and pool rules own results.
Recipe authors own hidden-dependency completeness. Small disposable scripts need
no recipe or duplicate-content bookkeeping.

## Rollback and cleanup

Before a mutation, associate its rollback journal with the test:

```sh
python scripts/workspace/artifact_workspace.py recovery --root ROOT --journal JOURNAL
```

After the operation-specific restoration helper verifies recovery, it attaches
its proof using the same command plus `--proof PROOF`. Missing or changed proof
blocks finish. The portable helper verifies proof identity, not the meaning of
restored state; adapt the project's real restoration checks. Restoration does
not release consumers. Keep only project-approved rolling baselines separately
from transient experiment snapshots; do not invent a universal backup schedule.

```sh
python scripts/workspace/artifact_workspace.py cleanup
python scripts/workspace/artifact_workspace.py cleanup --apply
```

Cleanup previews by default. Apply revalidates file identity/content and consumer
protection before retiring eligible closed-workspace payloads. Linked paths,
unknown historical files and files created after closeout require review.
Adoption, relocation and historical retirement need concrete review-only
proposals before mutation. Retained sources, active work, preservation and
unresolved writers/recovery remain protected.

Console lists are capped at 20 entries; the Python API retains complete results
for targeted automation.

The registry holds compact metadata and at most 1,000 retirement/assessment
receipts. A pre-deletion journal survives interrupted transactions and rotates
at 1 MiB with one previous segment; assess an interrupted retirement from file
presence plus its receipt. Neither store contains payload copies or per-run reports. Closed identities remain for
provenance; stale recipe rows and completed closed-job rows are pruned during
apply. Shared dependency/tool caches and versioned releases have their own
documented retention owners; per-experiment caches remain transient. Add
project-specific capture, baseline and external-tool retention through this
authority rather than a second cleanup system.
