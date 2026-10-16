# Session Learning 0.8.0 Validation

Development records and model-evaluation tools stay outside distributable skills. Raw evaluation prompts and model logs remain in the ignored `temp_windows_live_fixture` directory; canonical stores and production activity never retain them.

## Automated contracts

The Windows run passed 254 tests with:

```text
rtk uv run --cache-dir temp_windows_live_fixture/uv-cache python -m unittest discover -s tests/session-learning -q
```

This includes the existing retrieval, migration, transaction, packaging, host-launcher, and performance contracts, plus 36 extension tests covering configuration/consent, conditional exposure, capture privacy/lifecycle/deduplication, permission isolation, backlog warning/pagination, receipt replay/recovery, concurrent activity/retention, stable reflection coverage, and transactional consolidation. The skill creator's `quick_validate.py` also passed. No remote workflows were run; native macOS/Linux and application-level host receipt remain outside this local run's coverage.

Activity reports cover the most recent 90 calendar days. Successful aggregate writes prune expired files; inactive hosts or permission failures can delay physical cleanup, while reports still exclude expired data. No background expiry job is installed.

A model pilot found that staging validation required an instruction pointer before the canonical transaction could create it. The fresh-project regression now verifies successful active acceptance, pointer creation, receipt-backed disposition, and final structural validation. Preparation checks field contracts without requiring future managed projections; transaction validation still checks their actual contents before commit. Rejected handoff records return bounded actionable validation details.

## Disabled-mode comparison

The fixed baseline is local commit `479f083c438840bbef6558d478ba5ac1563c7688`. One hundred warm engine events per setting, plus compaction, resume, and pre-tool probes, produced identical lesson context with drafting disabled. Project canonical bytes remained unchanged.

| Setting | Median (ms) | p95 (ms) |
| --- | ---: | ---: |
| Baseline | 11.52 | 13.89 |
| Disabled drafting, audit default on | 13.61 | 27.99 |
| Disabled drafting, audit off | 12.81 | 18.69 |

The measured median increase with default auditing was 2.10 ms, within the declared 20 ms warm-engine budget. This single Windows sample, taken while model evaluation was running, does not establish universal latency or cold launcher performance. Existing packaged-launcher deadline checks passed separately.

Reproduce with:

```text
rtk uv run --cache-dir temp_windows_live_fixture/uv-cache python tests/session-learning/benchmark_extension_hooks.py --baseline-ref 479f083c438840bbef6558d478ba5ac1563c7688 --output temp_windows_live_fixture/hook-comparison-new
```

## Behavioral comparison design

The fixed fixture file defines eight multi-session trajectories, three repetitions, and four arms: baseline, drafting, reflection, and combined (96 trajectories). Seeded learning labels and expected paths are withheld from models. Meaningful successes, corrections, non-lessons, unresolved verification, long sessions, context loss, and cross-authority disagreement are represented.

`run_extension_cohorts.py` freezes baseline/candidate runtime trees and fixture hashes before the run. GPT-6-Sol at low reasoning processes eight separate project stores in each arm/repetition cohort. Work, retrospective, reflection/control, and reuse have fresh contexts; helper feedback remains within each phase. Reflection arms also receive a separate repeated reflection to measure churn. Semantic choices come from models, while the harness supplies deterministic IDs/timestamps and invokes actual engine operations. Draft instruction requests, saves, acceptance receipts, canonical authoring, snapshot maintenance, and hooks use the real runtime.

Shared cohort context creates correlation and amortizes instruction/transport costs; there are only three independent cohort repetitions per arm. The harness measures bounded decision tasks rather than executed code changes. It supports dynamically retrieved lessons, not workflow-skill authoring. Context restoration is simulated. Helper requests and model usage expose fixture overhead, but transport time cannot establish production-task interference. Path scores measure the selected input, not complete procedural correctness. Verification is scored separately so conservative reporting of unexecuted planned work is not penalized as an incorrect path choice.

Production counters cannot establish missed capture or effectiveness. Seeded relevance estimates capture precision/recall; accepted/reviewed counts separately describe review yield. Failed future path choices identify potential repeated corrections, rather than proving that a human actually issued another correction. No statistically established performance gain is claimed.

Reproduce in a fresh ignored directory:

```text
rtk uv run --cache-dir temp_windows_live_fixture/uv-cache python tests/session-learning/run_extension_cohorts.py --baseline-ref 479f083c438840bbef6558d478ba5ac1563c7688 --output temp_windows_live_fixture/learning-comparison-new
rtk uv run --cache-dir temp_windows_live_fixture/uv-cache python tests/session-learning/summarize_extension_evaluation.py temp_windows_live_fixture/learning-comparison-new/results.json --output temp_windows_live_fixture/learning-comparison-new/summary.json
```

`run_extension_behavioral.py` additionally supports individual native tool-use trajectories when investigating a specific fixture; its latency and tool-use measurements should not be mixed with cohort measurements. Transport/protocol pilots are excluded from the fixed comparison.

## Completed behavioral outcomes

All 96 trajectories completed. Compact results, runtime/fixture hashes, per-fixture scores, phase costs, and coverage limits are saved in [extension_behavioral_results_0_8_0.json](../../tests/session-learning/extension_behavioral_results_0_8_0.json).

| Arm | Exact primary paths | Exact reuse paths | Drafts / seeded relevant drafts | Reviewed / accepted | Repeat reflection changed records |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 22/24 | 5/24 | — | — | — |
| Drafting | 22/24 | 6/24 | 21/21 | 21/15 | — |
| Reflection | 22/24 | 3/24 | — | — | 0 |
| Combined | 22/24 | 5/24 | 21/21 | 20/15 | 0 |

Both capture arms had 100% seeded recall and precision, with no routine-work drafts. Accepted/reviewed yield was 71.4% for drafting and 75% for combined; deferred, dismissed, and one unreviewed observation remained visible. One stale acceptance request was rejected in the combined arm. All reuse artifacts correctly reported that new verification was unavailable. Exact path scores are stricter than semantic correctness and can penalize different interpretations of the temporary/destination settings files.

Each capture arm made 42 work-phase helper requests: 21 instruction loads and 21 saves. Drafting emitted 44,032 hook-context characters plus 67,158 full-instruction characters across its 24 trajectories; combined emitted 43,744 plus 67,158. These totals include long fixture paths and three session-boundary pointers per project. Reflection-only emitted 837 hook-context characters; baseline predates production activity counters and has no comparable production audit measurement. Instruction/schema/context supplied by the evaluation itself is reported separately through CLI usage in the results artifact.

| Arm | Cohort elapsed mean ± sample SD (s) | Range (s), three cohorts |
| --- | ---: | ---: |
| Baseline | 77.12 ± 4.13 | 72.35–79.55 |
| Drafting | 109.59 ± 12.94 | 101.89–124.53 |
| Reflection | 127.44 ± 14.03 | 111.30–136.65 |
| Combined | 178.66 ± 21.11 | 165.10–202.98 |

Times include model transport and additional repeated reflection in reflection arms. They are cohort measurements, not independent per-project latency samples.

Capture worked more consistently than subsequent usefulness. Several accepted active lessons were not emitted for differently phrased future requests; for example, a `client response change` trigger did not match a generated-client field-addition request. This identifies a question about trigger quality and retrieval coverage, not proof that drafting or reflection improved performance. The reuse phase did not permit native file discovery, manual index lookup, or pre-tool retrieval, so it understates the routes available during real repository work. Compacted observations sometimes remained deferred because supporting verification was unavailable in the review context. Reflection preserved bytes on these small healthy stores; transactional consolidation is validated structurally, but this behavioral set does not establish a consolidation benefit. Future behavioral work should use native repository tasks and examine trigger/review quality before changing capture methodology.

The behavioral runtime was frozen at SHA-256 `284a7700c778370fe766b88defb64de1e7a6939eaf137a723ba027853345ff9e`. Final implementation adds three safeguards tested separately: recheck queued-save consent under the writer lock, measure hooks in projects without learning stores, and prevent parent consent/retrieval from crossing a nested Git boundary. These conditions were absent from the fixed behavioral fixtures; all 254 automated tests cover the final implementation. The results artifact retains the original frozen hash rather than relabeling it as the final runtime.
