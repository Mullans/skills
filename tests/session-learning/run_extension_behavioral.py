"""Real model evaluation, kept outside installed skills.

Each trajectory uses four fresh model contexts: work/capture, retrospective,
reflection (or an equal neutral task), and reuse. Real helper writes and hook
emissions are inspected afterward. Gold capture labels are withheld from agents.
This is a decision-artifact fixture suite, not a substitute for production coding
performance or real host compaction acceptance testing.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "plugins/mullans-productivity/skills/session-learning"
PREFIX = "plugins/mullans-productivity/skills/session-learning/"


def engine(skill, identity):
    spec = importlib.util.spec_from_file_location(identity, skill / "scripts/session_learning.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_baseline(target, revision):
    # Revision must be fixed before the run; read-only local Git, no fetch.
    files = subprocess.check_output(["rtk", "proxy", "git", "-c", f"safe.directory={REPO.as_posix()}",
                                    "-C", str(REPO), "ls-tree", "-r", "--name-only", revision, "--", PREFIX], text=True).splitlines()
    for file in files:
        destination = target / file[len(PREFIX):]
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = subprocess.check_output(["rtk", "proxy", "git", "-c", f"safe.directory={REPO.as_posix()}",
                                          "-C", str(REPO), "show", f"{revision}:{file}"])
        destination.write_bytes(content)


def invoke(args, directory, prompt, phase):
    command = [args.codex, "exec", "--ignore-user-config", "--ephemeral", "--disable", "plugins",
               "--disable", "remote_plugin", "--disable", "apps", "--disable", "hooks",
               "--disable", "multi_agent", "--disable", "unbounded_connection_retries",
               "--enable", "skip_host_skill_discovery", "-c", "suppress_unstable_features_warning=true",
               "--json", "--skip-git-repo-check", "--approve-for-me", "-C", str(directory), "-"]
    if getattr(args, "model", None):
        command[2:2] = ["--model", args.model, "-c", f'model_reasoning_effort="{args.reasoning_effort}"']
    if os.name == "nt":
        command[2:2] = ["-c", "windows.sandbox=elevated"]
    started = time.monotonic()
    result = subprocess.run(command, input=prompt, text=True, encoding="utf-8", capture_output=True, timeout=args.timeout)
    # Development artifacts only. Never install these logs in runtime memory.
    (directory / f"{phase}.events.jsonl").write_text(result.stdout, encoding="utf-8")
    (directory / f"{phase}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    completed = [v for v in events if v.get("type") == "turn.completed"]
    if result.returncode or not completed:
        raise RuntimeError(f"model phase {phase} unavailable; see development logs")
    return {"seconds": time.monotonic() - started,
            "tool_calls": sum(v.get("type") == "item.completed" and v.get("item", {}).get("type") in
                              {"command_execution", "file_change", "mcp_tool_call"} for v in events),
            "usage": completed[-1].get("usage", {})}


def artifact(directory, name):
    try:
        return json.loads((directory / name).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def success(value, fixture):
    return set(value.get("edit_inputs", [])) == set(fixture["expected_inputs"]) and value.get("verification_status") == fixture["expected_verification"]


def conflict_records(e, root, home):
    for authority, statement in (("project", "Select the parser dialect in dialect-settings.json."),
                                 ("local", "Hardcode the dialect in parser.json.")):
        proof = {"schema_version": 2, "record_type": "evidence", "id": "evidence.dialect", "authority": authority,
                 "session_id": "seed-session", "signal": "durable_user_convention", "situation": "Dialect selection.",
                 "attempted_behavior": "Selected a dialect.", "feedback": statement, "corrected_behavior": statement,
                 "outcome": "Parser checks passed.", "created_at": "2026-10-01T00:00:00Z"}
        lesson = {"schema_version": 4, "record_type": "lesson", "id": "lesson.dialect", "authority": authority,
                  "version": e.SKILL_VERSION, "equivalence_key": None, "conflict_targets": [], "conflict_history": [],
                  "title": "Dialect selection", "statement": statement, "kind": "guardrail", "status": "active",
                  "scope": {"type": "paths", "paths": ["parser.json", "dialect-settings.json"]},
                  "triggers": ["dialect update"], "anti_pattern": [], "safe_path": [statement], "exceptions": [],
                  "delivery": {"mode": "dynamic", "host": None, "path": None,
                               "instruction_path": "AGENTS.md" if authority == "project" else None, "enforcement_target": None},
                  "provenance": [{"evidence_id": proof["id"], "signal": proof["signal"]}],
                  "relationships": {"supersedes": [], "related": []},
                  "usage": {"eligible_sessions": 0, "confirmations": 0, "violations": 0, "repeat_corrections": 0,
                            "last_eligible_at": None, "last_confirmed_at": None, "last_violated_at": None},
                  "timestamps": {"created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-01T00:00:00Z"}}
        e.apply_manifest(root, {"manifest_schema_version": 2, "origin": "current_session", "changes": [
            {"path": ".session-learning/evidence/evidence.dialect.json", "json": proof},
            {"path": ".session-learning/lessons/lesson.dialect.json", "json": lesson}]}, authority=authority, home_dir=home)


def trajectory(args, fixture, arm, repetition, baseline):
    directory = args.output / f"{fixture['id']}-{arm}-{repetition}"
    if directory.exists():
        raise ValueError("trajectory workspace exists; choose a fresh output directory")
    root, home, data = directory / "project", directory / "home", directory / "host-data"
    for path in (root, home, data):
        path.mkdir(parents=True)
    skill = directory / "runtime"
    shutil.copytree(baseline if arm == "baseline" else SKILL, skill, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    e = engine(skill, "evaluation_engine")
    enabled = arm in {"drafting", "combined"}
    if arm != "baseline":
        e._extensions().configure(e, root, home=home, drafting=enabled)
    else:
        (root / ".session-learning").mkdir()
    if fixture.get("seed_conflict"):
        conflict_records(e, root, home)
    # A convenient shell-independent helper pins fixture paths and Python.
    wrapper = directory / "learning.py"
    wrapper.write_text("import runpy,sys\nsys.dont_write_bytecode=True\n"
        f"sys.argv=[{str(skill / 'scripts/session_learning.py')!r},*sys.argv[1:],'--root',{str(root)!r},'--home-dir',{str(home)!r}]\n"
        f"runpy.run_path({str(skill / 'scripts/session_learning.py')!r},run_name='__main__')\n", encoding="utf-8")
    common = (f"Work only within {directory}. Python executable: {sys.executable}. "
              f"Learning helper: {wrapper}; its root/home arguments are already pinned. "
              "Keep the primary requested artifact in the project directory. Do not delegate, access remote services, or edit runtime files.\n")
    common += "Do not stage or commit fixture artifacts or access the enclosing repository. All shell commands must start with rtk; use rtk proxy powershell for PowerShell or rtk uv for Python.\n"
    common += "edit_inputs names directly edited inputs; put generation steps/outputs in followup_steps. Verification refers to the available observation, not a claim of a new run.\n"
    def hook(event, session, **extra):
        return e.handle_hook_event({"hook_event_name": event, "cwd": str(root), "session_id": session, **extra},
                                   host="codex", data_dir=data, home_dir=home).get("hookSpecificOutput", {}).get("additionalContext", "")
    emitted = hook("SessionStart", "work-session", source="startup")
    visible = [{"id": v["id"], "text": v["text"]} for v in fixture["events"]]
    visible.extend({"id": f"event.routine.{i}", "text": f"Routine label update {i} passed the unchanged check; no new insight."}
                   for i in range(fixture.get("distractor_events", 0)))
    work_prompt = common + emitted + "\nVisible session: work-session; events:\n" + json.dumps(visible) + "\n" + fixture["task"]
    phases = {"work": invoke(args, directory, work_prompt, "work")}
    first = artifact(root, "task-result.json")
    if not first:
        raise RuntimeError("primary artifact unavailable; tool/policy failures cannot be scored as product outcomes")
    if arm != "baseline":
        captured = e._extensions().drafts(e, root, home)[0]
    else:
        captured = []
    hook("SessionEnd", "work-session")
    # The compaction fixture intentionally withholds the early observation from
    # the next context; staged evidence can survive it, inferred history cannot.
    retained = [] if fixture.get("compact") else visible
    restoration = hook("SessionStart", "retro-session", source="compact" if fixture.get("compact") else "startup")
    retro_prompt = common + restoration + f"\nUse $session-learning at {skill / 'SKILL.md'} for an explicit retrospective. "
    retro_prompt += "Visible session summary: " + json.dumps(retained) + ". Primary artifact: " + json.dumps(first)
    retro_prompt += ". Review available pending drafts, preserve verification gaps, and report uncovered context."
    # Baseline has no draft helpers; do not request a feature it never had.
    if arm == "baseline":
        retro_prompt = retro_prompt.replace("Review available pending drafts, ", "")
    phases["retrospective"] = invoke(args, directory, retro_prompt, "retrospective")
    hook("SessionEnd", "retro-session")
    if arm in {"reflection", "combined"}:
        reflect_prompt = common + f"Use $session-learning at {skill / 'SKILL.md'} for explicit reflection of existing canonical guidance. "
        reflect_prompt += "Report grounded changes or no-op and unresolved findings; do not codify new observations."
    else:
        reflect_prompt = common + "Inspect task-result.json and briefly report its existing verification status. Make no changes."
    phases["reflection_or_control"] = invoke(args, directory, reflect_prompt, "reflection")
    lesson_bytes = {p: p.read_bytes() for name in ("project", "local") for p in e.store_path(root, authority=name, home_dir=home).glob("lessons/*.json")}
    reuse_context = hook("SessionStart", "reuse-session", source="resume") + hook("UserPromptSubmit", "reuse-session", prompt=fixture["reuse"])
    phases["reuse"] = invoke(args, directory, common + reuse_context + "\nNo new verification has been supplied in this phase.\n" + fixture["reuse"] + " Write reuse-result.json.", "reuse")
    reused = artifact(root, "reuse-result.json")
    hook("SessionEnd", "reuse-session")
    review = e._extensions().drafts(e, root, home)[0] if arm != "baseline" else []
    wanted = {v["id"] for v in fixture["events"] if v["learning"]}
    captured_ids = {event for record in captured for event in record["source"]["event_ids"]}
    useful = [record for record in captured if wanted & set(record["source"]["event_ids"])]
    return {"fixture": fixture["id"], "arm": arm, "repetition": repetition, "status": "complete", "phases": phases,
            "primary_decision_success": success(first, fixture), "reuse_decision_success": set(reused.get("edit_inputs", [])) == set(fixture["expected_inputs"]) and reused.get("verification_status") == "unverified",
            "seeded_learning_moments": len(wanted), "seeded_moments_captured": len(wanted & captured_ids),
            "drafts_captured": len(captured), "drafts_matching_seeded_moments": len(useful),
            "reviewed_drafts": sum(v["review_reason"] is not None for v in review),
            "accepted_drafts": sum(v["disposition"] == "accepted" for v in review),
            "deferred_drafts": sum(v["disposition"] == "deferred" for v in review),
            "canonical_lesson_count": len(lesson_bytes),
            "activity": e._extensions().activity(e, root, home=home, data_dir=data) if arm != "baseline" else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high"])
    args = parser.parse_args()
    args.output = args.output.resolve()
    allowed = REPO / "temp_windows_live_fixture" if os.name == "nt" else REPO / "temp_macos_live_fixture"
    if not args.output.is_relative_to(allowed):
        raise ValueError("evaluation output must use the repository's ignored live-fixture area")
    if not args.codex:
        raise ValueError("Codex CLI unavailable")
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = args.output / "baseline-runtime"
    install_baseline(baseline, args.baseline_ref)
    spec = json.loads(Path(__file__).with_name("extension_behavioral_fixtures.json").read_text())
    schedule = [(fixture, arm, repetition) for repetition in range(1, spec["repetitions"] + 1)
                for fixture in spec["fixtures"] for arm in spec["arms"]]
    results = []
    report = {"schema_version": 1, "baseline_ref": args.baseline_ref, "planned_trajectories": len(schedule),
              "coverage": "decision artifacts; simulated context restoration; manual semantic review still required", "results": results}
    for fixture, arm, repetition in schedule[:args.limit] if args.limit else schedule:
        print(f"Running {fixture['id']} {arm} repetition {repetition}", flush=True)
        try:
            results.append(trajectory(args, fixture, arm, repetition, baseline))
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
            results.append({"fixture": fixture["id"], "arm": arm, "repetition": repetition, "status": "incomplete", "error": str(exc)})
            report["stopped_reason"] = "fixture or model transport failure; incomplete trajectories are not scored"
        (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        if results[-1]["status"] != "complete":
            return 1
    for arm in spec["arms"]:
        arm_results = [v for v in results if v["arm"] == arm]
        values = [sum(phase["seconds"] for phase in v["phases"].values()) for v in arm_results]
        if values:
            report.setdefault("duration_variability", {})[arm] = {"n": len(values), "mean": statistics.mean(values),
                "minimum": min(values), "maximum": max(values), "stdev": statistics.stdev(values) if len(values) > 1 else None}
    (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
