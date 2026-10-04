"""96 bounded model trajectories with real engine mutations, outside distribution.

Eight isolated project stores share a model call per phase/arm/repetition. Four
fresh phases (work, retrospective, reflection/control, reuse) are retained; tool
feedback is carried only within a phase. This reduces transport cost but creates
within-cohort correlation. These decision tasks do not measure production coding
success, native host delivery, or isolated per-project latency. No gold labels
are sent to the model. Metadata serialization is deterministic; all semantic
capture, promotion, reconciliation, and maintenance decisions come from models.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time

from run_extension_behavioral import engine, install_baseline, invoke, conflict_records, REPO, SKILL

sys.dont_write_bytecode = True


def tree_hash(path):
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            digest.update(file.relative_to(path).as_posix().encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def records(e, root, home):
    return {authority: {kind: [e._public_record(v) for v in e._load_records(
        e.store_path(root, authority=authority, home_dir=home), kind)[0]]
        for kind in ("lessons", "evidence", "cases")} for authority in ("project", "local")}


def canonical(e, root, home):
    return {authority + ":" + file.relative_to(e.store_path(root, authority=authority, home_dir=home)).as_posix():
            hashlib.sha256(file.read_bytes()).hexdigest()
            for authority in ("project", "local")
            for directory in ("lessons", "evidence", "cases")
            for file in e.store_path(root, authority=authority, home_dir=home).glob(directory + "/*.json")}


def result_text(directory, phase):
    events = [json.loads(line) for line in (directory / f"{phase}.events.jsonl").read_text(encoding="utf-8").splitlines()]
    messages = [v["item"]["text"] for v in events if v.get("type") == "item.completed"
                and v.get("item", {}).get("type") == "agent_message"]
    value = messages[-1].strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(value)


def serialize_lesson(e, spec, identity):
    # Metadata defaults are serialization, never semantic decisions or proof.
    authority = spec["authority"]
    proof = {"schema_version": 2, "record_type": "evidence", "id": "evidence." + identity,
             "authority": authority, "session_id": "work-session", "signal": spec["signal"],
             **spec["observation"], "created_at": "2026-10-04T00:00:00Z"}
    guidance = spec["guidance"]
    lesson = {"schema_version": 4, "record_type": "lesson", "id": "lesson." + identity,
              "authority": authority, "version": e.SKILL_VERSION, "equivalence_key": None,
              "conflict_targets": [], "conflict_history": [], "title": spec["title"],
              "statement": guidance["statement"], "kind": spec["kind"], "status": spec["status"],
              "scope": guidance["scope"], "triggers": guidance["triggers"],
              "anti_pattern": spec.get("anti_pattern", []), "safe_path": guidance["safe_path"],
              "exceptions": guidance["exceptions"],
              "delivery": {"mode": "dynamic" if spec["status"] == "active" else "none", "host": None,
                           "path": None, "instruction_path": "AGENTS.md" if authority == "project" and spec["status"] == "active" else None,
                           "enforcement_target": None},
              "provenance": [{"evidence_id": proof["id"], "signal": proof["signal"]}],
              "relationships": {"supersedes": [], "related": []},
              "usage": {"eligible_sessions": 0, "confirmations": 0, "violations": 0, "repeat_corrections": 0,
                        "last_eligible_at": None, "last_confirmed_at": None, "last_violated_at": None},
              "timestamps": {"created_at": "2026-10-04T00:00:00Z", "updated_at": "2026-10-04T00:00:00Z"}}
    return {"manifest_schema_version": 2, "origin": "current_session", "changes": [
        {"path": f".session-learning/evidence/{proof['id']}.json", "json": proof},
        {"path": f".session-learning/lessons/{lesson['id']}.json", "json": lesson}]}


def cohort(args, spec, arm, repetition, source):
    directory = args.output / f"{arm}-{repetition}"
    directory.mkdir()
    skill = directory / "runtime"
    shutil.copytree(source, skill)
    e = engine(skill, "cohort_engine")
    home, data = directory / "home", directory / "host-data"
    home.mkdir(); data.mkdir()
    enabled = arm in {"drafting", "combined"}
    projects = {}
    def hook(item, event, session, **extra):
        return e.handle_hook_event({"hook_event_name": event, "cwd": str(item["root"]), "session_id": session, **extra},
                host="codex", home_dir=home, data_dir=data).get("hookSpecificOutput", {}).get("additionalContext", "")
    for fixture in spec["fixtures"]:
        root = directory / fixture["id"]
        root.mkdir()
        if arm != "baseline":
            e._extensions().configure(e, root, home=home, drafting=enabled)
        else:
            (root / ".session-learning").mkdir()
        if fixture.get("seed_conflict"):
            conflict_records(e, root, home)
        visible = [{"id": v["id"], "text": v["text"]} for v in fixture["events"]]
        visible.extend({"id": f"event.routine.{i}", "text": f"Routine label update {i} passed unchanged checks; no new insight."}
                       for i in range(fixture.get("distractor_events", 0)))
        projects[fixture["id"]] = {"root": root, "fixture": fixture, "visible": visible,
                                   "hook": "", "artifact": None, "reuse": None, "captured": [], "errors": []}
        projects[fixture["id"]]["hook"] = hook(projects[fixture["id"]], "SessionStart", "work-session", source="startup")
    common = ("This is a bounded model evaluation with eight independent projects. Each project's facts and guidance apply only to it. "
              "Use only supplied information and helper feedback; do not run native tools, read files, access other projects, delegate, or use Git. "
              "The harness executes the helper calls you request against real isolated stores. Return ONLY JSON as {\"actions\":[...]}. "
              "Each action requires project (the supplied ID), op, and arguments. Primary artifacts require edit_inputs, followup_steps, "
              "verification_status (verified/unverified). edit_inputs means directly edited inputs; generated outputs belong in followup_steps. "
              "Verification reports observations actually available in this phase, never invented new checks. "
              "Session ID is work-session, source host codex. Do not infer facts from project IDs.\n")
    phases = {}
    requests = []
    def run(phase, instructions, context, allowed, rounds=3):
        transcript = common + instructions + "\nAvailable operations: " + allowed + "\nProjects:\n" + json.dumps(context)
        telemetry = []
        for turn in range(rounds):
            name = f"{phase}-{turn}"
            telemetry.append(invoke(args, directory, transcript, name))
            response = result_text(directory, name)
            actions = response.get("actions")
            if not isinstance(actions, list):
                raise ValueError("model returned no action list")
            feedback, failures = [], 0
            for action in actions:
                pid = action["project"]
                if pid not in projects:
                    raise ValueError("unknown project in model action")
                item, op, arguments = projects[pid], action["op"], action.get("arguments", {})
                root = item["root"]
                try:
                    if phase == "work" and op == "artifact":
                        if set(arguments) == {"result"}:
                            arguments = arguments["result"]
                        item["artifact"] = {key: arguments[key] for key in ("edit_inputs", "followup_steps", "verification_status")}
                        (root / "task-result.json").write_text(json.dumps(item["artifact"], indent=2), encoding="utf-8")
                        outcome = {"written": True}
                    elif phase == "reuse" and op == "artifact":
                        if set(arguments) == {"result"}:
                            arguments = arguments["result"]
                        item["reuse"] = {key: arguments[key] for key in ("edit_inputs", "followup_steps", "verification_status")}
                        (root / "reuse-result.json").write_text(json.dumps(item["reuse"], indent=2), encoding="utf-8")
                        outcome = {"written": True}
                    elif phase == "work" and enabled and op == "draft-context":
                        outcome = e._extensions().draft_context(e, root, home=home, data_dir=data)
                    elif phase == "work" and enabled and op == "save-draft":
                        outcome = e._extensions().save_draft(e, root, arguments, home=home, data_dir=data)
                    elif phase == "retrospective" and op in {"create-lesson", "accept-draft"}:
                        model_spec = arguments["lesson"]
                        identity = f"evaluation.{pid}.{arguments.get('identity', '001')}"
                        manifest = serialize_lesson(e, model_spec, identity)
                        if op == "accept-draft" and arm != "baseline":
                            outcome = e._extensions().accept_draft(e, root, arguments["draft_id"], arguments["expected_sha256"],
                                        manifest, home=home, data_dir=data, reason=arguments.get("reason", "useful_new"))
                        else:
                            outcome = e.apply_manifest(root, manifest, authority=model_spec["authority"], home_dir=home)
                    elif phase == "retrospective" and arm != "baseline" and op == "review-draft":
                        outcome = e._extensions().review_draft(e, root, arguments["draft_id"], arguments["expected_sha256"],
                                    arguments["disposition"], arguments["reason"], home=home, data_dir=data)
                    elif phase == "retrospective" and op == "apply-manifest":
                        outcome = e.apply_manifest(root, arguments["manifest"], authority=arguments["authority"], home_dir=home)
                    elif phase.startswith("reflection") and arm in {"reflection", "combined"} and op == "apply-manifest":
                        outcome = e.apply_manifest(root, arguments["manifest"], authority=arguments["authority"], home_dir=home)
                    elif phase != "work" and phase != "reuse" and op == "audit":
                        outcome = e.audit_store(root, authority="both", home_dir=home)
                    elif op == "report":
                        outcome = {"reported": arguments}
                        item.setdefault("reports", {}).setdefault(phase, []).append(arguments)
                    else:
                        raise ValueError("operation unavailable in this phase/project")
                    feedback.append({"project": pid, "op": op, "result": outcome})
                    requests.append({"phase": phase, "project": pid, "op": op, "success": True})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    failures += 1
                    item["errors"].append({"phase": phase, "op": op, "error": str(exc)})
                    feedback.append({"project": pid, "op": op, "error": str(exc)})
                    requests.append({"phase": phase, "project": pid, "op": op, "success": False})
            missing = any(item["artifact" if phase == "work" else "reuse"] is None for item in projects.values()) if phase in {"work", "reuse"} else False
            if not failures and not missing and not any(a["op"] == "draft-context" for a in actions):
                break
            transcript += "\nYour previous response: " + json.dumps(response) + "\nReal helper feedback: " + json.dumps(feedback)
            transcript += "\nFinish remaining decisions; do not repeat successful mutations. Return an empty action list if done."
        phases[phase] = telemetry
    work_context = [{"project": pid, "hook_context": v["hook"], "events": v["visible"], "task": v["fixture"]["task"]}
                    for pid, v in projects.items()]
    work_ops = "artifact(arguments=result object), report(arguments=concise finding)"
    if enabled:
        work_ops += ", draft-context(arguments={}), save-draft(arguments=payload documented by draft-context)"
    run("work", "Carry out each primary task; follow supplied hook context when relevant.", work_context, work_ops)
    for item in projects.values():
        if item["artifact"] is None:
            raise RuntimeError("missing primary artifact; not a scorable trajectory")
        if arm != "baseline":
            item["captured"] = e._extensions().drafts(e, item["root"], home)[0]
        hook(item, "SessionEnd", "work-session")
    policy = "\n".join((skill / name).read_text(encoding="utf-8") for name in [
        "SKILL.md", "references/decision-policy.md", "references/authority-routing.md", "references/patch-authoring.md"])
    if arm != "baseline":
        policy += (skill / "references/draft-review.md").read_text(encoding="utf-8")
    contexts = []
    for pid, item in projects.items():
        contexts.append({"project": pid, "visible_events": [] if item["fixture"].get("compact") else item["visible"],
                         "primary_artifact": item["artifact"], "canonical": records(e, item["root"], home),
                         "retrospective_context": e.retrospective_context(item["root"], "", home_dir=home),
                         **({"pending_drafts": e._extensions().pending(e, item["root"], home=home)} if arm != "baseline" else {})})
        hook(item, "SessionStart", "retro-session", source="compact" if item["fixture"].get("compact") else "startup")
    contract = ('Explicit retrospective. Apply the supplied skill gates to visible evidence and pending drafts. '
        'Never infer missing observations from a task plan. Avoid duplicates and keep uncertain conclusions candidates. '
        'A create-lesson/accept-draft lesson spec contains authority, title, kind, status, signal, observation (five contrast fields), '
        'guidance {statement,scope {type,paths},triggers,safe_path,exceptions}, and optional anti_pattern. '
        'This helper authors dynamic or inactive lessons; kind must be guardrail, project_knowledge, preference, or invariant. '
        'Signal must be one of explicit_user_correction, test_failure, runtime_failure, ci_failure, review_finding, '
        'durable_user_convention, validated_workflow, successful_non_obvious_discovery. Status must be candidate or active. '
        'The harness fills only stable IDs/timestamps/version/delivery/provenance/zero usage; semantic choices are yours. '
        'For existing guidance use hash-guarded typed apply-manifest. Report no-op/deferrals/unresolved conflicts.\n')
    ops = 'create-lesson(arguments={lesson:spec,identity:short-unique-id}), apply-manifest(arguments={authority,manifest}), audit(arguments={}), report'
    if arm != "baseline":
        ops += ', accept-draft(arguments={draft_id,expected_sha256,lesson:spec,reason}), review-draft(arguments={draft_id,expected_sha256,disposition,reason})'
    run("retrospective", contract + policy, contexts, ops)
    for item in projects.values():
        hook(item, "SessionEnd", "retro-session")
        audit = e.audit_store(item["root"], authority="both", home_dir=home)
        if audit["load_errors"] or audit["validation_errors"]:
            raise RuntimeError("invalid canonical result")
    before_reflection = {pid: canonical(e, item["root"], home) for pid, item in projects.items()}
    def reflect(phase):
        if arm in {"reflection", "combined"}:
            context = [{"project": pid, "activity": e._extensions().activity(e, item["root"], home=home, data_dir=data),
                        "snapshot": e._extensions().reflection_context(e, item["root"], home=home),
                        "canonical": records(e, item["root"], home)} for pid, item in projects.items()]
            instructions = "Explicit reflection on canonical guidance. Existing evidence is supplied in full. Report coverage, grounded changes or no-op, unresolved findings. "
            instructions += policy + (skill / "references/reflection.md").read_text(encoding="utf-8")
            run(phase, instructions, context, "apply-manifest(arguments={authority,manifest}), audit(arguments={}), report")
        else:
            run(phase, "Report only the existing artifact verification status; make no changes.",
                [{"project": pid, "artifact": item["artifact"]} for pid, item in projects.items()], "report")
    reflect("reflection")
    after_reflection = {pid: canonical(e, item["root"], home) for pid, item in projects.items()}
    if arm in {"reflection", "combined"}:
        reflect("reflection-repeat")
    after_repeat = {pid: canonical(e, item["root"], home) for pid, item in projects.items()}
    run("reuse", "Carry out each task using only its supplied context. No additional verification was performed or supplied in this phase.",
        [{"project": pid, "hook_context": hook(item, "SessionStart", "reuse-session", source="resume") +
          hook(item, "UserPromptSubmit", "reuse-session", prompt=item["fixture"]["reuse"]), "task": item["fixture"]["reuse"]}
         for pid, item in projects.items()], "artifact(arguments=result object), report")
    results = []
    for pid, item in projects.items():
        hook(item, "SessionEnd", "reuse-session")
        fixture = item["fixture"]
        review = e._extensions().drafts(e, item["root"], home)[0] if arm != "baseline" else []
        wanted = {v["id"] for v in fixture["events"] if v["learning"]}
        captured_ids = {event for draft in item["captured"] for event in draft["source"]["event_ids"]}
        reused = item["reuse"] or {}
        paths = lambda value: set(value.get("edit_inputs", [])) == set(fixture["expected_inputs"])
        changed = lambda left, right: sum(left.get(key) != right.get(key) for key in set(left) | set(right))
        results.append({"fixture": pid, "arm": arm, "repetition": repetition, "status": "complete",
            "primary_path_success": paths(item["artifact"]),
            "primary_observation_verification_exact": item["artifact"].get("verification_status") == fixture["expected_verification"],
            "primary_verification_conservative": item["artifact"].get("verification_status") == "unverified" or fixture["expected_verification"] == "verified",
            "reuse_path_success": paths(reused), "reuse_verification_success": reused.get("verification_status") == "unverified",
            "seeded_learning_moments": len(wanted), "seeded_moments_captured": len(wanted & captured_ids),
            "drafts_captured": len(item["captured"]),
            "drafts_matching_seeded_moments": sum(bool(wanted & set(v["source"]["event_ids"])) for v in item["captured"]),
            "reviewed_drafts": sum(v["review_reason"] is not None for v in review),
            "accepted_drafts": sum(v["disposition"] == "accepted" for v in review),
            "deferred_drafts": sum(v["disposition"] == "deferred" for v in review),
            "reflection_changed_records": changed(before_reflection[pid], after_reflection[pid]),
            "repeat_reflection_changed_records": changed(after_reflection[pid], after_repeat[pid]),
            "helper_requests": [v for v in requests if v["project"] == pid], "errors": item["errors"],
            "activity": e._extensions().activity(e, item["root"], home=home, data_dir=data) if arm != "baseline" else None,
            "reports": item.get("reports", {})})
    return {"arm": arm, "repetition": repetition, "phases": phases, "results": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex", default=shutil.which("codex"))
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--model", default="gpt-6-sol")
    parser.add_argument("--reasoning-effort", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--limit-cohorts", type=int)
    args = parser.parse_args()
    args.output = args.output.resolve()
    allowed = REPO / ("temp_windows_live_fixture" if os.name == "nt" else "temp_macos_live_fixture")
    if not args.output.is_relative_to(allowed):
        raise ValueError("use ignored live-fixture area")
    args.output.mkdir(parents=True, exist_ok=False)
    baseline, candidate = args.output / "baseline-runtime", args.output / "candidate-runtime"
    install_baseline(baseline, args.baseline_ref)
    shutil.copytree(SKILL, candidate, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    spec = json.loads(Path(__file__).with_name("extension_behavioral_fixtures.json").read_text())
    report = {"schema_version": 1, "planned_trajectories": 96, "baseline_ref": args.baseline_ref,
              "model": args.model, "reasoning_effort": args.reasoning_effort,
              "candidate_runtime_sha256": tree_hash(candidate), "baseline_runtime_sha256": tree_hash(baseline),
              "fixture_sha256": hashlib.sha256(Path(__file__).with_name("extension_behavioral_fixtures.json").read_bytes()).hexdigest(),
              "coverage": "four fresh phases; within-cohort correlation; bounded model decision tasks and real helper execution; simulated restoration; no production task or native host claims",
              "cohorts": []}
    schedule = [(arm, repetition) for repetition in range(1, spec["repetitions"] + 1) for arm in spec["arms"]]
    for arm, repetition in schedule[:args.limit_cohorts] if args.limit_cohorts else schedule:
        print(f"Running cohort {arm} repetition {repetition}", flush=True)
        try:
            report["cohorts"].append(cohort(args, spec, arm, repetition, baseline if arm == "baseline" else candidate))
        except Exception as exc:
            report["stopped_reason"] = str(exc)
            (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise
        (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Completed {len(report['cohorts']) * 8}/96 trajectories", flush=True)
    report["duration_variability"] = {}
    for arm in spec["arms"]:
        values = [sum(v["seconds"] for rounds in c["phases"].values() for v in rounds) for c in report["cohorts"] if c["arm"] == arm]
        if values:
            report["duration_variability"][arm] = {"n_cohorts": len(values), "mean_seconds": statistics.mean(values),
                "minimum_seconds": min(values), "maximum_seconds": max(values),
                "stdev_seconds": statistics.stdev(values) if len(values) > 1 else None}
    (args.output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
