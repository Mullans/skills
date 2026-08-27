from __future__ import annotations

# Development-only validation for the distributable session-learning skill.

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


def find_repo_root(start: Path) -> Path:
    for parent in start.resolve().parents:
        if (parent / "plugins" / "mullans-productivity" / "skills").is_dir():
            return parent
    raise RuntimeError(f"Unable to find repository root from {start}")


REPO_ROOT = find_repo_root(Path(__file__))
SKILL_ROOT = REPO_ROOT / "plugins" / "mullans-productivity" / "skills" / "session-learning"
SCRIPT = SKILL_ROOT / "scripts" / "session_learning.py"
SCENARIOS = Path(__file__).with_name("behavioral_scenarios.json")
RESULTS = Path(__file__).with_name("behavioral_results.json")
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("session_learning", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
session_learning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_learning)


def usage(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "eligible_sessions": 0,
        "confirmations": 0,
        "violations": 0,
        "repeat_corrections": 0,
        "last_eligible_at": None,
        "last_confirmed_at": None,
        "last_violated_at": None,
    }
    value.update(overrides)
    return value


def evidence(evidence_id: str = "evidence.20260827.generated-files.001") -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "evidence",
        "id": evidence_id,
        "session_id": "session-2026-08-27",
        "signal": "explicit_user_correction",
        "situation": "An API response changed.",
        "attempted_behavior": "Edited generated TypeScript clients directly.",
        "feedback": "The schema is the source of truth.",
        "corrected_behavior": "Updated the schema and regenerated clients.",
        "outcome": "Targeted tests passed.",
        "created_at": "2026-08-27T12:00:00Z",
    }


def lesson(
    lesson_id: str = "lesson.generated-files.001",
    *,
    status: str = "active",
    kind: str = "guardrail",
    destination: dict[str, object] | None = None,
    provenance: list[dict[str, str]] | None = None,
    statement: str | None = None,
) -> dict[str, object]:
    if destination is None:
        destination = {
            "type": "instruction",
            "host": "codex",
            "path": "AGENTS.md",
        }
    return {
        "schema_version": 1,
        "record_type": "lesson",
        "id": lesson_id,
        "title": "Generated API clients",
        "statement": statement
        or "When changing generated API clients, update the schema and regenerate; do not edit generated output directly.",
        "kind": kind,
        "status": status,
        "scope": {
            "type": "paths",
            "paths": ["schemas/**", "src\\generated\\**"],
        },
        "triggers": ["generated clients", "API schema", "code generation"],
        "anti_pattern": ["direct edits to generated output"],
        "safe_path": ["update schema", "regenerate", "run targeted tests"],
        "exceptions": [],
        "destination": destination,
        "provenance": provenance
        if provenance is not None
        else [
            {
                "evidence_id": "evidence.20260827.generated-files.001",
                "signal": "explicit_user_correction",
            }
        ],
        "relationships": {"supersedes": [], "related": []},
        "usage": usage(),
        "timestamps": {
            "created_at": "2026-08-27T12:00:00Z",
            "updated_at": "2026-08-27T12:00:00Z",
        },
    }


def case_record() -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "case",
        "id": "case.generated-files.001",
        "lesson_ids": ["lesson.generated-files.001"],
        "situation": "A generated API client exposes an old response shape.",
        "trap": "Patch the generated client directly.",
        "expected": "Change the schema, regenerate, and verify the diff.",
        "created_at": "2026-08-27T12:00:00Z",
    }


class StoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def store(self) -> Path:
        return self.root / ".agents" / "learning"

    def write_record(self, folder: str, record: dict[str, object]) -> Path:
        target = self.store / folder / f"{record['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return target

    def write_instruction_projection(self, lesson_id: str = "lesson.generated-files.001") -> None:
        (self.root / "AGENTS.md").write_text(
            f"- Update schemas first. <!-- session-learning:{lesson_id} -->\n",
            encoding="utf-8",
        )

    def make_valid_store(self) -> None:
        self.write_record("evidence", evidence())
        self.write_record("lessons", lesson())
        self.write_record("cases", case_record())
        self.write_instruction_projection()
        session_learning.rebuild_index(self.root)

    def test_read_commands_do_not_initialize_an_empty_store(self) -> None:
        self.assertEqual([], session_learning.search_lessons(self.root, "generated"))
        self.assertEqual([], session_learning.validate_store(self.root))
        self.assertEqual(0, session_learning.audit_store(self.root)["total_lessons"])
        self.assertFalse(self.store.exists())

    def test_rebuild_index_refuses_empty_store_without_creating_files(self) -> None:
        with self.assertRaisesRegex(ValueError, "no lesson records"):
            session_learning.rebuild_index(self.root)
        self.assertFalse(self.store.exists())

    def test_valid_store_rebuilds_and_validates_deterministic_index(self) -> None:
        self.make_valid_store()
        first = (self.store / "index.md").read_text(encoding="utf-8")
        session_learning.rebuild_index(self.root)
        second = (self.store / "index.md").read_text(encoding="utf-8")

        self.assertEqual(first, second)
        self.assertIn("## Active lessons", first)
        self.assertIn("lesson.generated-files.001", first)
        self.assertIn("Candidates are not instructions", first)
        self.assertEqual([], session_learning.validate_store(self.root))

    def test_search_ranks_scope_and_trigger_matches(self) -> None:
        self.write_record("evidence", evidence())
        generated = lesson()
        packages = lesson(
            "lesson.package-manager.001",
            status="candidate",
            statement="Use pnpm for workspace package operations.",
            destination={"type": "instruction", "host": "codex", "path": "AGENTS.md"},
        )
        packages["title"] = "Workspace package manager"
        packages["scope"] = {"type": "repository", "paths": []}
        packages["triggers"] = ["pnpm", "workspace packages"]
        packages["anti_pattern"] = ["use another package manager"]
        packages["safe_path"] = ["use pnpm for workspace commands"]
        self.write_record("lessons", generated)
        self.write_record("lessons", packages)

        results = session_learning.search_lessons(self.root, "generated schema client")

        self.assertEqual("lesson.generated-files.001", results[0]["id"])
        self.assertEqual(1, len(results))

    def test_search_omits_unrelated_zero_score_lessons(self) -> None:
        self.write_record("lessons", lesson(provenance=[]))

        self.assertEqual([], session_learning.search_lessons(self.root, "unrelated typography"))

    def test_search_surfaces_malformed_records(self) -> None:
        target = self.store / "lessons" / "broken.json"
        target.parent.mkdir(parents=True)
        target.write_text("{broken", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "invalid JSON"):
            session_learning.search_lessons(self.root, "generated")

    def test_audit_reports_conflicts_measurement_and_orphan_evidence(self) -> None:
        active = lesson()
        active["usage"] = usage(eligible_sessions=3, violations=2, repeat_corrections=1)
        conflict = lesson(
            "lesson.generated-files-conflict.001",
            status="conflicted",
            provenance=[],
            destination={"type": "none", "host": None, "path": None},
        )
        self.write_record("lessons", active)
        self.write_record("lessons", conflict)
        self.write_record("evidence", evidence("evidence.orphan.001"))

        audit = session_learning.audit_store(self.root)

        self.assertEqual(2, audit["total_lessons"])
        self.assertEqual(1, audit["status_counts"]["conflicted"])
        self.assertEqual(2, audit["violations"])
        self.assertEqual(1, audit["repeat_corrections"])
        self.assertEqual(["lesson.generated-files-conflict.001"], audit["unresolved_conflicts"])
        self.assertEqual(["evidence.orphan.001"], audit["orphan_evidence"])

    def test_validate_detects_missing_evidence_and_invalid_measurement(self) -> None:
        broken = lesson()
        broken["usage"] = usage(eligible_sessions=-1)
        self.write_record("lessons", broken)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("missing evidence" in error for error in errors))
        self.assertTrue(any("eligible_sessions" in error for error in errors))

    def test_validate_rejects_provenance_signal_mismatch(self) -> None:
        self.write_record("evidence", evidence())
        mismatched = lesson()
        mismatched["provenance"] = [
            {
                "evidence_id": "evidence.20260827.generated-files.001",
                "signal": "validated_workflow",
            }
        ]
        self.write_record("lessons", mismatched)
        self.write_instruction_projection()
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("provenance signal does not match evidence" in error for error in errors))

    def test_validate_rejects_impossible_measurement_history(self) -> None:
        self.write_record("evidence", evidence())
        broken = lesson(status="candidate")
        broken["usage"] = usage(
            eligible_sessions=1,
            confirmations=2,
            violations=1,
            repeat_corrections=2,
        )
        self.write_record("lessons", broken)
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("confirmations + violations" in error for error in errors))
        self.assertTrue(any("repeat_corrections" in error for error in errors))
        self.assertTrue(any("last_eligible_at" in error for error in errors))
        self.assertTrue(any("last_confirmed_at" in error for error in errors))
        self.assertTrue(any("last_violated_at" in error for error in errors))

    def test_validate_detects_dangling_relationship_and_case(self) -> None:
        self.write_record("evidence", evidence())
        broken = lesson()
        broken["relationships"] = {
            "supersedes": ["lesson.missing.001"],
            "related": [],
        }
        self.write_record("lessons", broken)
        self.write_record("cases", case_record())
        self.write_instruction_projection()
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("lesson.missing.001" in error for error in errors))

    def test_validate_detects_stale_index(self) -> None:
        self.make_valid_store()
        (self.store / "index.md").write_text("stale\n", encoding="utf-8")

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("index.md is stale" in error for error in errors))

    def test_active_instruction_requires_matching_projection_marker(self) -> None:
        self.write_record("evidence", evidence())
        self.write_record("lessons", lesson())
        (self.root / "AGENTS.md").write_text("- Update schemas first.\n", encoding="utf-8")
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("projection marker" in error for error in errors))

    def test_active_context_requires_managed_index_pointer(self) -> None:
        self.write_record("evidence", evidence())
        context = lesson(
            "lesson.legacy-provider.001",
            kind="project_knowledge",
            destination={
                "type": "index",
                "host": "claude",
                "path": ".agents/learning/index.md",
                "instruction_path": "CLAUDE.md",
            },
        )
        self.write_record("lessons", context)
        (self.root / "CLAUDE.md").write_text("# Project\n", encoding="utf-8")
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("session-learning:index" in error for error in errors))

    def test_active_context_pointer_uses_host_native_instruction_file(self) -> None:
        self.write_record("evidence", evidence())
        context = lesson(
            "lesson.legacy-provider.001",
            kind="project_knowledge",
            destination={
                "type": "index",
                "host": "claude",
                "path": ".agents/learning/index.md",
                "instruction_path": "AGENTS.md",
            },
        )
        self.write_record("lessons", context)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:index -->\n", encoding="utf-8"
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("Claude index pointer" in error for error in errors))

    def test_active_workflow_requires_native_skill_marker(self) -> None:
        self.write_record("evidence", evidence())
        workflow = lesson(
            "lesson.add-provider-workflow.001",
            kind="workflow",
            destination={
                "type": "skill",
                "host": "claude",
                "path": ".claude/skills/add-provider/SKILL.md",
            },
        )
        self.write_record("lessons", workflow)
        skill = self.root / ".claude" / "skills" / "add-provider" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("# Add provider\n", encoding="utf-8")
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("projection marker" in error for error in errors))

    def test_active_status_rejects_non_authoritative_destination(self) -> None:
        self.write_record("evidence", evidence())
        active = lesson(destination={"type": "none", "host": None, "path": None})
        self.write_record("lessons", active)
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("active guardrail" in error for error in errors))

    def test_active_kind_requires_matching_destination_type(self) -> None:
        self.write_record("evidence", evidence())
        workflow = lesson(
            "lesson.workflow.001",
            kind="workflow",
            destination={"type": "instruction", "host": "codex", "path": "AGENTS.md"},
        )
        self.write_record("lessons", workflow)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.workflow.001 -->\n", encoding="utf-8"
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("active workflow" in error for error in errors))

    def test_active_projection_requires_host_native_path_and_valid_skill(self) -> None:
        self.write_record("evidence", evidence())
        workflow = lesson(
            "lesson.workflow.001",
            kind="workflow",
            destination={
                "type": "skill",
                "host": "codex",
                "path": ".claude/skills/workflow/SKILL.md",
            },
        )
        self.write_record("lessons", workflow)
        skill = self.root / ".claude" / "skills" / "workflow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "<!-- session-learning:lesson.workflow.001 -->\n# Missing metadata\n",
            encoding="utf-8",
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("Codex workflow skill" in error for error in errors))

    def test_active_workflow_requires_valid_skill_frontmatter(self) -> None:
        self.write_record("evidence", evidence())
        workflow = lesson(
            "lesson.workflow.001",
            kind="workflow",
            destination={
                "type": "skill",
                "host": "codex",
                "path": ".agents/skills/workflow/SKILL.md",
            },
        )
        self.write_record("lessons", workflow)
        skill = self.root / ".agents" / "skills" / "workflow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "<!-- session-learning:lesson.workflow.001 -->\n# Missing metadata\n",
            encoding="utf-8",
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("valid SKILL.md frontmatter" in error for error in errors))

    def test_active_automation_requires_existing_target(self) -> None:
        self.write_record("evidence", evidence())
        invariant = lesson(
            "lesson.rollback-check.001",
            kind="invariant",
            destination={
                "type": "automation",
                "host": "codex",
                "path": "tests/migration_rollback_test.py",
            },
        )
        self.write_record("lessons", invariant)
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("automation target is missing" in error for error in errors))

    def test_supersession_requires_consistent_lifecycle_and_removed_old_marker(self) -> None:
        self.write_record("evidence", evidence())
        old = lesson("lesson.package-manager-old.001")
        new = lesson("lesson.package-manager-new.001")
        new["relationships"] = {
            "supersedes": ["lesson.package-manager-old.001"],
            "related": [],
        }
        self.write_record("lessons", old)
        self.write_record("lessons", new)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.package-manager-old.001 -->\n"
            "<!-- session-learning:lesson.package-manager-new.001 -->\n",
            encoding="utf-8",
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("supersedes target must have status 'superseded'" in error for error in errors))

    def test_inactive_lesson_must_not_remain_projected(self) -> None:
        self.write_record("evidence", evidence())
        old = lesson("lesson.retired.001", status="retired")
        self.write_record("lessons", old)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.retired.001 -->\n", encoding="utf-8"
        )
        session_learning.rebuild_index(self.root)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("inactive lesson remains projected" in error for error in errors))

    def test_audit_includes_case_and_full_validation_errors(self) -> None:
        self.write_record("evidence", evidence())
        self.write_record("lessons", lesson())
        self.write_instruction_projection()
        case_path = self.store / "cases" / "broken.json"
        case_path.parent.mkdir(parents=True)
        case_path.write_text("{broken", encoding="utf-8")

        audit = session_learning.audit_store(self.root)

        self.assertTrue(any("invalid JSON" in error for error in audit["load_errors"]))
        self.assertTrue(audit["validation_errors"])

    def test_resolve_project_root_falls_back_to_non_git_working_directory(self) -> None:
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(self.root.resolve(), session_learning.resolve_project_root(None))
        finally:
            os.chdir(previous)

    def test_behavioral_results_cover_every_green_scenario(self) -> None:
        scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        results = json.loads(RESULTS.read_text(encoding="utf-8"))
        expected_ids = {item["id"] for item in scenarios["green_scenarios"]}
        result_ids = {item["id"] for item in results["results"]}

        self.assertEqual(1, results["schema_version"])
        self.assertEqual(expected_ids, result_ids)
        self.assertTrue(results["isolated_temporary_repositories"])
        self.assertTrue(results["runner"]["identifier"])
        self.assertTrue(results["runner"]["model"])
        implementation = results["implementation"]
        implementation_base = (
            REPO_ROOT if implementation.get("base") == "repository" else SKILL_ROOT
        )
        digest = hashlib.sha256()
        for relative_path in implementation["files"]:
            digest.update(relative_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update((implementation_base / relative_path).read_bytes())
            digest.update(b"\0")
        self.assertEqual(implementation["sha256"], digest.hexdigest())
        for result in results["results"]:
            self.assertEqual("pass", result["status"], result["id"])
            self.assertTrue(result["task_reference"], result["id"])
            self.assertTrue(result["fixture"], result["id"])
            self.assertTrue(result["validation"]["command"], result["id"])
            self.assertTrue(result["validation"]["outcome"], result["id"])
            self.assertTrue(result["checks"], result["id"])
            self.assertTrue(all(result["checks"].values()), result["id"])
        v2_expected = {item["id"] for item in scenarios["v2_green_scenarios"]}
        v2_results = results["v2_validation"]["results"]
        self.assertEqual(v2_expected, {item["id"] for item in v2_results})
        self.assertTrue(results["v2_validation"]["isolated_temporary_repositories"])
        for result in v2_results:
            self.assertEqual("pass", result["status"], result["id"])
            self.assertTrue(result["test_reference"], result["id"])

    def test_distributable_skill_contains_only_runtime_resources(self) -> None:
        self.assertFalse(SKILL_ROOT.joinpath("tests").exists())
        self.assertFalse(SKILL_ROOT.joinpath("references", "architecture.md").exists())
        self.assertFalse(any(path.name == "__pycache__" for path in SKILL_ROOT.rglob("__pycache__")))

    def test_runtime_policy_preserves_storage_and_no_op_invariants(self) -> None:
        policy = SKILL_ROOT.joinpath("references", "decision-policy.md").read_text(
            encoding="utf-8"
        )

        for relative_path in (
            ".agents/learning/lessons/<lesson-id>.json",
            ".agents/learning/evidence/<evidence-id>.json",
            ".agents/learning/cases/<case-id>.json",
            ".agents/learning/index.md",
        ):
            self.assertIn(relative_path, policy)
        self.assertIn("A no-op retrospective must be filesystem-neutral.", policy)


if __name__ == "__main__":
    unittest.main()
