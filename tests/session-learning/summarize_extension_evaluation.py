"""Compact observed metrics; source logs remain in ignored live fixtures."""
import argparse
import json
from pathlib import Path
import statistics


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize(report):
    cohorts = report["cohorts"]
    rows = [row for cohort in cohorts for row in cohort["results"]]
    result = {key: report[key] for key in ("baseline_ref", "candidate_runtime_sha256", "baseline_runtime_sha256",
                                         "fixture_sha256", "model", "reasoning_effort", "coverage")}
    result["completed_trajectories"] = len(rows)
    result["planned_trajectories"] = report["planned_trajectories"]
    result["complete"] = len(rows) == report["planned_trajectories"] and not report.get("stopped_reason")
    result["arms"] = {}
    for arm in ("baseline", "drafting", "reflection", "combined"):
        selected = [row for row in rows if row["arm"] == arm]
        arm_cohorts = [c for c in cohorts if c["arm"] == arm]
        total = lambda key: sum(v[key] for v in selected)
        counters = {}
        for row in selected:
            for name, count in (row.get("activity") or {}).get("counts", {}).items():
                counters[name] = counters.get(name, 0) + count
        durations = [sum(r["seconds"] for rounds in c["phases"].values() for r in rounds) for c in arm_cohorts]
        failures = [error for row in selected for error in row["errors"]]
        captures, matching = total("drafts_captured"), total("drafts_matching_seeded_moments")
        reviewed, accepted = total("reviewed_drafts"), total("accepted_drafts")
        result["arms"][arm] = {"trajectories": len(selected), "primary_path_successes": total("primary_path_success"),
            "primary_conservative_verification": total("primary_verification_conservative"),
            "reuse_path_successes": total("reuse_path_success"), "reuse_verification_successes": total("reuse_verification_success"),
            "drafts": captures, "seeded_capture_precision": ratio(matching, captures),
            "seeded_capture_recall": ratio(total("seeded_moments_captured"), total("seeded_learning_moments")) if arm in {"drafting", "combined"} else None,
            "reviewed_drafts": reviewed, "accepted_drafts": accepted, "deferred_drafts": total("deferred_drafts"),
            "accepted_per_reviewed": ratio(accepted, reviewed), "drafts_per_trajectory": ratio(captures, len(selected)),
            "reflection_changed_records": total("reflection_changed_records"),
            "repeat_reflection_changed_records": total("repeat_reflection_changed_records"),
            "rejected_helper_calls": len(failures), "work_helper_calls": sum(v["phase"] == "work" and v["op"] != "artifact"
                and v["op"] != "report" for row in selected for v in row["helper_requests"]),
            "engine_activity": counters,
            "cohort_duration_seconds": {"n": len(durations), "mean": statistics.mean(durations) if durations else None,
                "minimum": min(durations) if durations else None, "maximum": max(durations) if durations else None,
                "stdev": statistics.stdev(durations) if len(durations) > 1 else None},
            "phases": {phase: {"model_calls": sum(len(c["phases"].get(phase, [])) for c in arm_cohorts),
                "seconds": sum(v["seconds"] for c in arm_cohorts for v in c["phases"].get(phase, [])),
                "input_tokens": sum(v["usage"].get("input_tokens", 0) for c in arm_cohorts for v in c["phases"].get(phase, [])),
                "output_tokens": sum(v["usage"].get("output_tokens", 0) for c in arm_cohorts for v in c["phases"].get(phase, []))}
                for phase in {p for c in arm_cohorts for p in c["phases"]}},
            "fixtures": {fixture: {"n": sum(v["fixture"] == fixture for v in selected),
                "primary_path_successes": sum(v["primary_path_success"] for v in selected if v["fixture"] == fixture),
                "reuse_path_successes": sum(v["reuse_path_success"] for v in selected if v["fixture"] == fixture),
                "captures": sum(v["drafts_captured"] for v in selected if v["fixture"] == fixture)}
                for fixture in sorted({v["fixture"] for v in selected})}}
    result["limitations"] = [
        "Within-cohort shared context means trajectories are correlated; only three cohort repetitions per arm.",
        "Primary and reuse metrics score input-path decisions, not executed changes or full workflow correctness.",
        "Conservative primary verification accepts unverified planned work; reuse must be unverified without new observations.",
        "Capture recall is against fixed seeded events; precision uses seeded relevance and accepted/reviewed separately.",
        "Helper requests and model usage expose fixture overhead; elapsed time includes model transport and cannot establish production interference.",
        "Runtime character counts describe actual emissions; CLI token counts describe the evaluation's complete prompts.",
        "Context restoration is simulated; native host receipt/application and historical repeat corrections are not measured.",
        "Repeat reflection is an additional explicit review and its timing is reported separately.",
        "No statistically established performance gain is claimed."]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--release-runtime", type=Path, help="record final runtime separately from evaluated frozen runtime")
    args = parser.parse_args()
    result = summarize(json.loads(args.input.read_text(encoding="utf-8")))
    if args.release_runtime:
        from run_extension_cohorts import tree_hash
        result["final_runtime_sha256"] = tree_hash(args.release_runtime)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8", newline="\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
