"""Compare disabled drafting against a frozen pre-extension hook engine."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

from run_extension_behavioral import REPO, SKILL, engine, install_baseline


def seed(e, root):
    store = root / ".session-learning"
    store.mkdir(parents=True)
    lesson = {"schema_version": 4, "record_type": "lesson", "version": "0.7.0", "id": "lesson.source",
        "authority": "project", "equivalence_key": None, "conflict_targets": [], "conflict_history": [],
        "title": "Schema source", "statement": "Edit the source schema before generating the client.", "kind": "guardrail", "status": "active",
        "scope": {"type": "paths", "paths": ["schemas/**", "clients/**"]}, "triggers": ["generated client"],
        "anti_pattern": [], "safe_path": ["edit source", "regenerate", "verify contract"], "exceptions": [],
        "delivery": {"mode": "dynamic", "host": None, "path": None, "instruction_path": "AGENTS.md", "enforcement_target": None},
        "provenance": [{"evidence_id": "evidence.source", "signal": "explicit_user_correction"}],
        "relationships": {"supersedes": [], "related": []}, "usage": {"eligible_sessions": 0, "confirmations": 0,
            "violations": 0, "repeat_corrections": 0, "last_eligible_at": None, "last_confirmed_at": None, "last_violated_at": None},
        "timestamps": {"created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"}}
    (store / "lessons").mkdir()
    (store / "lessons/lesson.source.json").write_text(json.dumps(lesson), encoding="utf-8")
    (root / "AGENTS.md").write_text(e._instruction_pointer_block(), encoding="utf-8")
    e.rebuild_index(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--events", type=int, default=100)
    args = parser.parse_args()
    args.output = args.output.resolve()
    platform = "windows" if os.name == "nt" else "macos" if sys.platform == "darwin" else "linux"
    if not args.output.is_relative_to(REPO / f"temp_{platform}_live_fixture"):
        raise ValueError("use the ignored live-fixture area")
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = args.output / "baseline-runtime"
    install_baseline(baseline, args.baseline_ref)
    old, new = engine(baseline, "benchmark_baseline"), engine(SKILL, "benchmark_current")
    outputs, durations = {}, {}
    for name, e in (("baseline", old), ("disabled_default_audit", new), ("disabled_no_audit", new)):
        root, home, data = (args.output / name / item for item in ("project", "home", "data"))
        for path in (root, home, data):
            path.mkdir(parents=True)
        seed(e, root)
        if name == "disabled_no_audit":
            (root / ".session-learning/config.json").write_text(json.dumps({"schema_version": 1, "activity_audit_enabled": False}), encoding="utf-8")
        canonical_before = {p: p.read_bytes() for p in (root / ".session-learning").rglob("*") if p.is_file()}
        results, timings = [], []
        for number in range(args.events + 5):
            payload = {"hook_event_name": "UserPromptSubmit", "cwd": str(root), "session_id": f"session-{number}", "prompt": "Update a generated client."}
            started = time.perf_counter()
            result = e.handle_hook_event(payload, host="codex", data_dir=data, home_dir=home)
            elapsed = (time.perf_counter() - started) * 1000
            if number >= 5:
                timings.append(elapsed)
                results.append(result)
        for event, extra in (("SessionStart", {"source": "compact"}), ("SessionStart", {"source": "resume"}),
                             ("PreToolUse", {"tool_name": "Edit", "tool_input": {"file_path": str(root / "clients/generated.json")}})):
            results.append(e.handle_hook_event({"hook_event_name": event, "cwd": str(root), "session_id": "session-10", **extra},
                                             host="codex", data_dir=data, home_dir=home))
        if canonical_before != {p: p.read_bytes() for p in (root / ".session-learning").rglob("*") if p.is_file()}:
            raise AssertionError("hooks mutated canonical project files")
        outputs[name] = results
        durations[name] = {"median_ms": statistics.median(timings), "p95_ms": sorted(timings)[int(len(timings) * .95) - 1],
                           "minimum_ms": min(timings), "maximum_ms": max(timings), "events": len(timings)}
    equivalent = all(values == outputs["baseline"] for values in outputs.values())
    regression = durations["disabled_default_audit"]["median_ms"] - durations["baseline"]["median_ms"]
    report = {"baseline_ref": args.baseline_ref, "disabled_context_equivalent": equivalent, "timings": durations,
              "median_additional_ms": regression, "budget_additional_ms": 20,
              "limitations": "single Windows/macOS/Linux host, warm in-process engine; packaged launcher latency is tested separately"}
    (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if equivalent and regression < 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
