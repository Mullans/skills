from __future__ import annotations

import importlib.util
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


def find_repo_root(start: Path) -> Path:
    for parent in start.resolve().parents:
        if (parent / "plugins" / "mullans-productivity" / "skills").is_dir():
            return parent
    raise RuntimeError(f"Unable to find repository root from {start}")


REPO_ROOT = find_repo_root(Path(__file__))
SKILL_ROOT = REPO_ROOT / "plugins" / "mullans-productivity" / "skills" / "session-learning"
SCRIPT = SKILL_ROOT / "scripts" / "session_learning.py"
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("session_learning_v2", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT}")
session_learning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session_learning)


def usage() -> dict[str, object]:
    return {
        "eligible_sessions": 0,
        "confirmations": 0,
        "violations": 0,
        "repeat_corrections": 0,
        "last_eligible_at": None,
        "last_confirmed_at": None,
        "last_violated_at": None,
    }


def evidence() -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "evidence",
        "id": "evidence.20260827.generated-files.001",
        "session_id": "session-2026-08-27",
        "signal": "explicit_user_correction",
        "situation": "An API response changed.",
        "attempted_behavior": "Edited generated clients directly.",
        "feedback": "The schema is the source of truth.",
        "corrected_behavior": "Updated the schema and regenerated clients.",
        "outcome": "Targeted tests passed.",
        "created_at": "2026-08-27T12:00:00Z",
    }


def v1_lesson(*, scope_type: str = "paths") -> dict[str, object]:
    paths = ["schemas/**", "src/generated/**"] if scope_type == "paths" else []
    return {
        "schema_version": 1,
        "record_type": "lesson",
        "id": "lesson.generated-files.001",
        "title": "Generated API clients",
        "statement": "Update the schema and regenerate clients; never edit generated output directly.",
        "kind": "guardrail",
        "status": "active",
        "scope": {"type": scope_type, "paths": paths},
        "triggers": ["generated clients", "API schema", "code generation"],
        "anti_pattern": ["direct edits to generated output"],
        "safe_path": ["update schema", "regenerate", "run targeted tests"],
        "exceptions": [],
        "destination": {"type": "instruction", "host": "codex", "path": "AGENTS.md"},
        "provenance": [
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


class SessionLearningV2StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / ".agents" / "learning"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_record(self, folder: str, record: dict[str, object]) -> Path:
        target = self.store / folder / f"{record['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return target

    def seed_v1(self, *, scope_type: str = "paths") -> Path:
        self.write_record("evidence", evidence())
        path = self.write_record("lessons", v1_lesson(scope_type=scope_type))
        (self.root / "AGENTS.md").write_text(
            "# Project\n\n"
            "<!-- session-learning:lesson.generated-files.001 -->\n"
            "- Update schemas first.\n",
            encoding="utf-8",
        )
        session_learning.rebuild_index(self.root)
        return path

    def test_migration_converts_scoped_instruction_to_dynamic_and_is_idempotent(self) -> None:
        lesson_path = self.seed_v1()

        first = session_learning.migrate_store(self.root, host="codex")
        second = session_learning.migrate_store(self.root, host="codex")

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertEqual(2, migrated["schema_version"])
        self.assertNotIn("destination", migrated)
        self.assertEqual("dynamic", migrated["delivery"]["mode"])
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])
        instructions = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("session-learning:lesson.generated-files.001", instructions)
        self.assertIn("session-learning:index", instructions)
        self.assertEqual([], session_learning.validate_store(self.root))

    def test_activate_both_uses_claude_import_bridge_without_copying_lesson(self) -> None:
        self.seed_v1()

        session_learning.activate_store(self.root, host="both")

        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        claude = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("session-learning:index", agents)
        self.assertEqual("@AGENTS.md\n", claude)
        self.assertNotIn("Update the schema", claude)

    def test_activate_empty_repository_is_filesystem_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")

            result = session_learning.activate_store(root, host="both")

            self.assertFalse(result["changed"])
            self.assertFalse((root / ".agents" / "learning").exists())
            self.assertFalse((root / "CLAUDE.md").exists())

    def test_activate_auto_prefers_codex_identity_when_compatibility_variables_coexist(self) -> None:
        lesson_path = self.seed_v1()

        with mock.patch.dict(
            os.environ,
            {"PLUGIN_ROOT": "codex-root", "CLAUDE_PLUGIN_ROOT": "compat-root"},
            clear=False,
        ):
            session_learning.activate_store(self.root, host="auto")

        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertEqual("AGENTS.md", record["delivery"]["instruction_path"])
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_repository_wide_instruction_remains_static_during_migration(self) -> None:
        lesson_path = self.seed_v1(scope_type="repository")

        session_learning.migrate_store(self.root, host="codex")

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertEqual("static", migrated["delivery"]["mode"])
        self.assertEqual("codex", migrated["delivery"]["host"])
        self.assertEqual("AGENTS.md", migrated["delivery"]["path"])
        self.assertIn(
            "session-learning:lesson.generated-files.001",
            (self.root / "AGENTS.md").read_text(encoding="utf-8"),
        )

    def test_migration_maps_workflow_and_automation_delivery_modes(self) -> None:
        self.write_record("evidence", evidence())
        workflow = v1_lesson()
        workflow["id"] = "lesson.generated-workflow.001"
        workflow["title"] = "Generated client workflow"
        workflow["kind"] = "workflow"
        workflow["destination"] = {
            "type": "skill",
            "host": "codex",
            "path": ".agents/skills/generated-workflow/SKILL.md",
        }
        automation = v1_lesson()
        automation["id"] = "lesson.generated-enforcement.001"
        automation["title"] = "Generated client enforcement"
        automation["kind"] = "invariant"
        automation["destination"] = {
            "type": "automation",
            "host": None,
            "path": "tests/generated_check.py",
        }
        workflow_path = self.write_record("lessons", workflow)
        automation_path = self.write_record("lessons", automation)
        skill = self.root / ".agents" / "skills" / "generated-workflow" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\nname: generated-workflow\ndescription: Regenerate clients.\n---\n"
            "<!-- session-learning:lesson.generated-workflow.001 -->\n",
            encoding="utf-8",
        )
        target = self.root / "tests" / "generated_check.py"
        target.parent.mkdir()
        target.write_text("# enforcement target\n", encoding="utf-8")

        session_learning.migrate_store(self.root, host="codex")

        migrated_workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        migrated_automation = json.loads(automation_path.read_text(encoding="utf-8"))
        self.assertEqual("workflow", migrated_workflow["delivery"]["mode"])
        self.assertEqual("automation", migrated_automation["delivery"]["mode"])
        self.assertEqual("tests/generated_check.py", migrated_automation["delivery"]["enforcement_target"])
        self.assertEqual([], session_learning.validate_store(self.root))

    def test_deactivate_retires_lesson_and_removes_static_projection(self) -> None:
        lesson_path = self.seed_v1(scope_type="repository")
        session_learning.migrate_store(self.root, host="codex")

        session_learning.deactivate_lesson(self.root, "lesson.generated-files.001")

        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertEqual("retired", record["status"])
        self.assertEqual("none", record["delivery"]["mode"])
        self.assertNotIn(
            "session-learning:lesson.generated-files.001",
            (self.root / "AGENTS.md").read_text(encoding="utf-8"),
        )

    def test_missing_static_marker_is_reported_without_mutating_record(self) -> None:
        lesson_path = self.seed_v1(scope_type="repository")
        session_learning.migrate_store(self.root, host="codex")
        before = lesson_path.read_bytes()
        (self.root / "AGENTS.md").write_text("# Project\n", encoding="utf-8")

        report = session_learning.reconcile_delivery(self.root, host="codex", apply=False)

        self.assertEqual(before, lesson_path.read_bytes())
        self.assertEqual(["lesson.generated-files.001"], report["missing_static"])

    def test_transaction_restores_original_files_when_post_write_validation_fails(self) -> None:
        lesson_path = self.seed_v1()
        before_lesson = lesson_path.read_bytes()
        before_agents = (self.root / "AGENTS.md").read_bytes()

        with self.assertRaisesRegex(ValueError, "forced validation failure"):
            session_learning.apply_file_transaction(
                self.root,
                {
                    lesson_path: b"changed\n",
                    self.root / "AGENTS.md": b"changed instructions\n",
                },
                validator=lambda: ["forced validation failure"],
            )

        self.assertEqual(before_lesson, lesson_path.read_bytes())
        self.assertEqual(before_agents, (self.root / "AGENTS.md").read_bytes())
        self.assertFalse((self.store / ".transactions").exists())

    def test_recovery_restores_interrupted_transaction_snapshot(self) -> None:
        lesson_path = self.seed_v1()
        original = lesson_path.read_bytes()
        transaction = self.store / ".transactions" / "interrupted"
        transaction.mkdir(parents=True)
        (transaction / "0000.bak").write_bytes(original)
        (transaction / "journal.json").write_text(
            json.dumps(
                {
                    "transaction_schema_version": 1,
                    "files": [
                        {
                            "path": lesson_path.relative_to(self.root).as_posix(),
                            "existed": True,
                            "backup": "0000.bak",
                            "original_sha256": hashlib.sha256(original).hexdigest(),
                            "replacement_sha256": hashlib.sha256(b"partially written\n").hexdigest(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        lesson_path.write_text("partially written\n", encoding="utf-8")

        recovered = session_learning.recover_transactions(self.root)

        self.assertEqual(1, recovered)
        self.assertEqual(original, lesson_path.read_bytes())
        self.assertFalse((self.store / ".transactions").exists())

    def test_recovery_discards_pre_journal_transaction_without_touching_files(self) -> None:
        lesson_path = self.seed_v1()
        original = lesson_path.read_bytes()
        transaction = self.store / ".transactions" / "snapshots-only"
        transaction.mkdir(parents=True)
        (transaction / "0000.bak").write_bytes(original)

        recovered = session_learning.recover_transactions(self.root)

        self.assertEqual(0, recovered)
        self.assertEqual(original, lesson_path.read_bytes())
        self.assertFalse((self.store / ".transactions").exists())

    def test_recovery_rejects_snapshot_hash_mismatch(self) -> None:
        lesson_path = self.seed_v1()
        transaction = self.store / ".transactions" / "corrupt"
        transaction.mkdir(parents=True)
        (transaction / "0000.bak").write_bytes(b"corrupt")
        (transaction / "journal.json").write_text(
            json.dumps(
                {
                    "transaction_schema_version": 1,
                    "files": [
                        {
                            "path": lesson_path.relative_to(self.root).as_posix(),
                            "existed": True,
                            "backup": "0000.bak",
                            "original_sha256": hashlib.sha256(b"different").hexdigest(),
                            "replacement_sha256": None,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        before = lesson_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "backup hash mismatch"):
            session_learning.recover_transactions(self.root)

        self.assertEqual(before, lesson_path.read_bytes())

    def test_static_to_dynamic_round_trip_removes_rule_and_keeps_pointer(self) -> None:
        self.seed_v1(scope_type="repository")
        session_learning.migrate_store(self.root, host="codex")

        session_learning.set_delivery(
            self.root, "lesson.generated-files.001", "dynamic", host="codex"
        )

        content = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("session-learning:lesson.generated-files.001", content)
        self.assertIn("session-learning:index", content)
        self.assertEqual([], session_learning.validate_store(self.root))

    def test_apply_manifest_updates_records_and_index_in_one_transaction(self) -> None:
        lesson_path = self.seed_v1()
        session_learning.migrate_store(self.root, host="codex")
        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        record["statement"] = "Change the schema, regenerate clients, and verify the generated diff."

        result = session_learning.apply_manifest(
            self.root,
            {
                "manifest_schema_version": 1,
                "changes": [
                    {
                        "path": lesson_path.relative_to(self.root).as_posix(),
                        "json": record,
                    }
                ],
            },
        )

        self.assertTrue(result["changed"])
        self.assertIn("verify the generated diff", (self.store / "index.md").read_text())
        self.assertEqual([], session_learning.validate_store(self.root))

    def test_apply_manifest_with_identical_content_is_filesystem_neutral(self) -> None:
        lesson_path = self.seed_v1()
        session_learning.migrate_store(self.root, host="codex")
        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        before_lesson = lesson_path.read_bytes()
        before_index = (self.store / "index.md").read_bytes()

        result = session_learning.apply_manifest(
            self.root,
            {
                "manifest_schema_version": 1,
                "changes": [
                    {
                        "path": lesson_path.relative_to(self.root).as_posix(),
                        "json": record,
                    }
                ],
            },
        )

        self.assertFalse(result["changed"])
        self.assertEqual([], result["files"])
        self.assertEqual(before_lesson, lesson_path.read_bytes())
        self.assertEqual(before_index, (self.store / "index.md").read_bytes())
        self.assertFalse((self.store / ".transactions").exists())

    def test_apply_manifest_rejects_paths_outside_learning_surfaces(self) -> None:
        self.seed_v1()
        with self.assertRaisesRegex(ValueError, "unsupported transaction path"):
            session_learning.apply_manifest(
                self.root,
                {
                    "manifest_schema_version": 1,
                    "changes": [{"path": "src/app.py", "content": "changed"}],
                },
            )


class SessionLearningV2HookTests(SessionLearningV2StorageTests):
    def setUp(self) -> None:
        super().setUp()
        self.data_dir = self.root / ".hook-data"
        self.home_dir = self.root / ".home"
        self.seed_v1()
        session_learning.migrate_store(self.root, host="codex")

    def event(self, event_name: str, **values: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "session_id": "session-a",
            "cwd": str(self.root),
            "hook_event_name": event_name,
        }
        payload.update(values)
        return payload

    def handle(self, event_name: str, *, host: str = "codex", **values: object) -> dict[str, object]:
        return session_learning.handle_hook_event(
            self.event(event_name, **values),
            host=host,
            data_dir=self.data_dir,
            home_dir=self.home_dir,
        )

    @staticmethod
    def context(result: dict[str, object]) -> str:
        output = result.get("hookSpecificOutput", {})
        if not isinstance(output, dict):
            return ""
        value = output.get("additionalContext", "")
        return value if isinstance(value, str) else ""

    def test_prompt_trigger_injects_only_active_matching_lesson(self) -> None:
        result = self.handle(
            "UserPromptSubmit", prompt="Please update the generated clients from the API schema."
        )

        self.assertIn("lesson.generated-files.001", self.context(result))
        self.assertIn("Update the schema and regenerate", self.context(result))

    def test_weak_lexical_match_and_irrelevant_prompt_do_not_inject(self) -> None:
        self.assertEqual({}, self.handle("UserPromptSubmit", prompt="Update the client meeting notes."))
        self.assertEqual({}, self.handle("UserPromptSubmit", prompt="Fix typography in the README."))

    def test_pre_tool_path_match_injects_but_same_turn_does_not_repeat(self) -> None:
        first = self.handle("UserPromptSubmit", prompt="Work on generated clients")
        second = self.handle(
            "PreToolUse",
            tool_name="Edit",
            tool_input={"file_path": str(self.root / "src" / "generated" / "client.ts")},
        )

        self.assertIn("lesson.generated-files.001", self.context(first))
        self.assertEqual({}, second)

    def test_five_prompt_cooldown_reinjects_on_fifth_subsequent_prompt(self) -> None:
        query = "Update generated clients from the API schema"
        self.assertTrue(self.context(self.handle("UserPromptSubmit", prompt=query)))
        for _ in range(4):
            self.assertEqual({}, self.handle("UserPromptSubmit", prompt=query))
        self.assertTrue(self.context(self.handle("UserPromptSubmit", prompt=query)))

    def test_compaction_and_resume_restore_context_while_clear_resets_it(self) -> None:
        query = "Update generated clients from the API schema"
        self.handle("UserPromptSubmit", prompt=query)

        compact = self.handle("SessionStart", source="compact")
        resume = self.handle("SessionStart", source="resume")
        cleared = self.handle("SessionStart", source="clear")

        self.assertIn("lesson.generated-files.001", self.context(compact))
        self.assertIn("lesson.generated-files.001", self.context(resume))
        self.assertEqual({}, cleared)
        self.assertTrue(self.context(self.handle("UserPromptSubmit", prompt=query)))

    def test_project_config_overrides_personal_config(self) -> None:
        personal = self.home_dir / ".agents" / "session-learning" / "config.json"
        personal.parent.mkdir(parents=True)
        personal.write_text(
            json.dumps({"schema_version": 1, "retrieval_enabled": True}), encoding="utf-8"
        )
        project = self.store / "config.json"
        project.write_text(
            json.dumps({"schema_version": 1, "retrieval_enabled": False}), encoding="utf-8"
        )

        result = self.handle(
            "UserPromptSubmit", prompt="Update generated clients from the API schema"
        )

        self.assertEqual({}, result)

    def test_project_config_exposes_an_absolute_python_path(self) -> None:
        personal = self.home_dir / ".agents" / "session-learning" / "config.json"
        personal.parent.mkdir(parents=True)
        personal.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "python_path": str(self.home_dir / "personal-python"),
                }
            ),
            encoding="utf-8",
        )
        configured = str(Path(sys.executable).resolve())
        (self.store / "config.json").write_text(
            json.dumps({"schema_version": 1, "python_path": configured}),
            encoding="utf-8",
        )

        config = session_learning._load_config(self.root, self.home_dir)

        self.assertEqual(configured, config["python_path"])

    def test_config_rejects_a_python_command_instead_of_an_executable_path(self) -> None:
        (self.store / "config.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "python_path": f'{sys.executable} -c "print(1)"',
                }
            ),
            encoding="utf-8",
        )

        config = session_learning._load_config(self.root, self.home_dir)

        self.assertIsNone(config["python_path"])

    def test_static_projection_suppression_is_scoped_to_current_host_visibility(self) -> None:
        session_learning.set_delivery(
            self.root, "lesson.generated-files.001", "static", host="codex"
        )
        query = "Update generated clients from the API schema"

        codex = self.handle("UserPromptSubmit", host="codex", prompt=query)
        claude_without_bridge = self.handle("UserPromptSubmit", host="claude", prompt=query)
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        claude_with_bridge = session_learning.handle_hook_event(
            self.event("UserPromptSubmit", session_id="session-b", prompt=query),
            host="claude",
            data_dir=self.data_dir,
            home_dir=self.home_dir,
        )

        self.assertEqual({}, codex)
        self.assertIn("lesson.generated-files.001", self.context(claude_without_bridge))
        self.assertIn("projection", str(claude_without_bridge.get("systemMessage", "")))
        self.assertEqual({}, claude_with_bridge)

    def test_nested_static_projection_suppresses_only_when_instruction_is_applicable(self) -> None:
        lesson_path = self.store / "lessons" / "lesson.generated-files.001.json"
        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        record["delivery"] = {
            "mode": "static",
            "host": "codex",
            "path": "backend/AGENTS.md",
            "instruction_path": None,
            "enforcement_target": None,
        }
        lesson_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        nested = self.root / "backend"
        nested.mkdir()
        (nested / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.generated-files.001 -->\n",
            encoding="utf-8",
        )
        query = "Update generated clients from the API schema"

        root_result = self.handle("UserPromptSubmit", prompt=query)
        nested_payload = self.event(
            "UserPromptSubmit",
            session_id="nested-session",
            cwd=str(nested),
            prompt=query,
        )
        nested_result = session_learning.handle_hook_event(
            nested_payload,
            host="codex",
            data_dir=self.data_dir,
            home_dir=self.home_dir,
        )

        self.assertIn("lesson.generated-files.001", self.context(root_result))
        self.assertEqual({}, nested_result)

    def test_projection_drift_diagnostic_is_once_per_session_and_never_mutates_lesson(self) -> None:
        session_learning.set_delivery(
            self.root, "lesson.generated-files.001", "static", host="codex"
        )
        lesson_path = self.store / "lessons" / "lesson.generated-files.001.json"
        before = lesson_path.read_bytes()
        (self.root / "AGENTS.md").write_text("# Missing marker\n", encoding="utf-8")

        first = self.handle(
            "UserPromptSubmit", prompt="Update generated clients from the API schema"
        )
        compact = self.handle("SessionStart", source="compact")

        self.assertIn("projection", str(first.get("systemMessage", "")))
        self.assertNotIn("systemMessage", compact)
        self.assertEqual(before, lesson_path.read_bytes())

    def test_concurrent_same_session_events_deliver_a_lesson_once(self) -> None:
        payload = self.event(
            "PreToolUse",
            tool_name="Edit",
            tool_input={"file_path": str(self.root / "src" / "generated" / "client.ts")},
        )

        def invoke(_: int) -> dict[str, object]:
            return session_learning.handle_hook_event(
                payload,
                host="codex",
                data_dir=self.data_dir,
                home_dir=self.home_dir,
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(invoke, range(8)))

        delivered = [result for result in results if self.context(result)]
        self.assertEqual(1, len(delivered))
        self.assertFalse(list(self.data_dir.glob("*.lock")))

    def test_state_is_project_and_session_scoped_and_retains_no_event_text(self) -> None:
        secret_prompt = "Update generated clients using secret phrase ALBATROSS"
        self.handle("UserPromptSubmit", prompt=secret_prompt)
        session_learning.handle_hook_event(
            self.event(
                "UserPromptSubmit",
                session_id="session-b",
                prompt="Update generated clients from API schema",
            ),
            host="codex",
            data_dir=self.data_dir,
            home_dir=self.home_dir,
        )

        states = sorted(self.data_dir.glob("state-*.json"))
        self.assertEqual(2, len(states))
        serialized = "\n".join(path.read_text(encoding="utf-8") for path in states)
        self.assertNotIn("ALBATROSS", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertTrue(all(json.loads(path.read_text())["state_schema_version"] == 1 for path in states))

    def test_session_end_removes_state_and_prunes_stale_state(self) -> None:
        self.handle("UserPromptSubmit", prompt="Update generated clients from API schema")
        self.assertTrue(list(self.data_dir.glob("state-*.json")))
        stale = self.data_dir / "state-stale-project-stale-session.json"
        stale.write_text(
            json.dumps(
                {
                    "state_schema_version": 1,
                    "prompt_sequence": 1,
                    "delivered": {},
                    "relevant": [],
                    "updated_at": "2020-01-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        old = time.time() - (31 * 24 * 60 * 60)
        os.utime(stale, (old, old))

        result = self.handle("SessionEnd", reason="other")

        self.assertEqual({}, result)
        self.assertFalse(list(self.data_dir.glob("state-*.json")))

    def test_unknown_host_and_missing_store_fail_open(self) -> None:
        self.assertEqual(
            {},
            session_learning.handle_hook_event(
                self.event("UserPromptSubmit", prompt="generated clients"),
                host="other",
                data_dir=self.data_dir,
                home_dir=self.home_dir,
            ),
        )
        with tempfile.TemporaryDirectory() as empty_directory:
            empty = Path(empty_directory) / "nested"
            empty.mkdir(parents=True)
            payload = self.event("UserPromptSubmit", prompt="generated clients")
            payload["cwd"] = str(empty)
            self.assertEqual(
                {},
                session_learning.handle_hook_event(
                    payload,
                    host="codex",
                    data_dir=self.data_dir,
                    home_dir=self.home_dir,
                ),
            )

    def test_candidates_and_conflicts_are_never_injected(self) -> None:
        lesson_path = self.store / "lessons" / "lesson.generated-files.001.json"
        record = json.loads(lesson_path.read_text(encoding="utf-8"))
        for status in ("candidate", "conflicted"):
            record["status"] = status
            record["delivery"] = {
                "mode": "none",
                "host": None,
                "path": None,
                "instruction_path": None,
                "enforcement_target": None,
            }
            lesson_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            self.assertEqual(
                {},
                session_learning.handle_hook_event(
                    self.event(
                        "UserPromptSubmit",
                        session_id=f"session-{status}",
                        prompt="Update generated clients from API schema",
                    ),
                    host="codex",
                    data_dir=self.data_dir,
                    home_dir=self.home_dir,
                ),
            )

    def test_workflow_automation_and_none_delivery_modes_are_never_injected(self) -> None:
        lesson_path = self.store / "lessons" / "lesson.generated-files.001.json"
        base = json.loads(lesson_path.read_text(encoding="utf-8"))
        deliveries = {
            "workflow": {
                "mode": "workflow",
                "host": "codex",
                "path": ".agents/skills/generated-workflow/SKILL.md",
                "instruction_path": None,
                "enforcement_target": None,
            },
            "automation": {
                "mode": "automation",
                "host": None,
                "path": None,
                "instruction_path": None,
                "enforcement_target": "tests/generated_check.py",
            },
            "none": {
                "mode": "none",
                "host": None,
                "path": None,
                "instruction_path": None,
                "enforcement_target": None,
            },
        }
        for mode, delivery in deliveries.items():
            record = dict(base)
            record["delivery"] = delivery
            lesson_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            result = session_learning.handle_hook_event(
                self.event(
                    "UserPromptSubmit",
                    session_id=f"delivery-{mode}",
                    prompt="Update generated clients from the API schema",
                ),
                host="codex",
                data_dir=self.data_dir,
                home_dir=self.home_dir,
            )
            self.assertEqual({}, result, mode)

    def test_windows_backslash_path_matches_normalized_scope(self) -> None:
        result = self.handle(
            "PreToolUse",
            tool_name="PowerShell",
            tool_input={"file_path": "src\\generated\\client.ts"},
        )

        self.assertIn("lesson.generated-files.001", self.context(result))

    def test_invalid_state_schema_is_discarded(self) -> None:
        state_path = session_learning._state_path(self.data_dir, self.root, "session-a")
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({"state_schema_version": 999, "prompt_sequence": 100}),
            encoding="utf-8",
        )

        result = self.handle(
            "UserPromptSubmit", prompt="Update generated clients from API schema"
        )

        self.assertIn("lesson.generated-files.001", self.context(result))
        self.assertEqual(1, json.loads(state_path.read_text())["prompt_sequence"])

    def test_context_limits_number_of_lessons_and_characters(self) -> None:
        for index in range(2, 7):
            record = json.loads(
                (self.store / "lessons" / "lesson.generated-files.001.json").read_text()
            )
            record["id"] = f"lesson.generated-files.{index:03d}"
            record["title"] = f"Generated client rule {index}"
            record["provenance"] = []
            self.write_record("lessons", record)
        config = self.store / "config.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "max_lessons_per_event": 2,
                    "max_context_characters": 600,
                }
            ),
            encoding="utf-8",
        )
        session_learning.rebuild_index(self.root)

        result = self.handle(
            "UserPromptSubmit", prompt="Update generated clients from API schema"
        )

        context = self.context(result)
        self.assertLessEqual(context.count("[lesson."), 2)
        self.assertLessEqual(len(context), 600)

    def test_warm_retrieval_with_500_lessons_stays_below_acceptance_budget(self) -> None:
        template = json.loads(
            (self.store / "lessons" / "lesson.generated-files.001.json").read_text()
        )
        for index in range(2, 501):
            record = dict(template)
            record["id"] = f"lesson.performance.{index:03d}"
            record["title"] = f"Unrelated performance lesson {index}"
            record["statement"] = f"Use unrelated operation {index}."
            record["triggers"] = [f"unique-trigger-{index}"]
            record["scope"] = {"type": "paths", "paths": [f"area-{index}/**"]}
            record["provenance"] = []
            self.write_record("lessons", record)
        session_learning.rebuild_index(self.root)
        payload = self.event(
            "UserPromptSubmit", prompt="Update generated clients from API schema"
        )
        cold_started = time.perf_counter()
        session_learning.handle_hook_event(
            payload,
            host="codex",
            data_dir=self.data_dir,
            home_dir=self.home_dir,
        )
        cold_elapsed = time.perf_counter() - cold_started
        warm_samples: list[float] = []
        for index in range(20):
            payload["session_id"] = f"performance-session-{index}"
            started = time.perf_counter()
            session_learning.handle_hook_event(
                payload,
                host="codex",
                data_dir=self.data_dir,
                home_dir=self.home_dir,
            )
            warm_samples.append(time.perf_counter() - started)
        warm_p95 = sorted(warm_samples)[18]

        self.assertLess(cold_elapsed, 0.5)
        self.assertLess(warm_p95, 0.1)


class SessionLearningV2PackagingTests(unittest.TestCase):
    @staticmethod
    def seed_dynamic_project(project: Path, *, instruction_path: str) -> None:
        lessons = project / ".agents" / "learning" / "lessons"
        lessons.mkdir(parents=True)
        record = v1_lesson()
        record.pop("destination")
        record["schema_version"] = 2
        record["delivery"] = {
            "mode": "dynamic",
            "host": None,
            "path": None,
            "instruction_path": instruction_path,
            "enforcement_target": None,
        }
        (lessons / f"{record['id']}.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

    def test_generated_host_hook_configs_are_current(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools" / "session-learning" / "generate_hooks.py"),
                "--root",
                str(REPO_ROOT),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_readme_documents_user_configuration_before_development_notes(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        user_notes, development_notes = readme.split("## Development Notes", maxsplit=1)

        self.assertIn("### Session Learning", user_notes)
        self.assertIn(".agents/learning/config.json", user_notes)
        self.assertIn("~/.agents/session-learning/config.json", user_notes)
        self.assertIn("cooldown_user_prompts", user_notes)
        self.assertIn("python_path", user_notes)
        self.assertNotIn("python_path", development_notes)

    def test_shared_plugin_boundary_bundles_both_host_adapters(self) -> None:
        plugin_root = REPO_ROOT / "plugins" / "mullans-productivity"
        expected_events = {"UserPromptSubmit", "PreToolUse", "SessionStart", "SessionEnd"}
        hook_paths = {
            "codex": plugin_root / "hooks" / "codex.json",
            "claude": plugin_root / "hooks" / "claude.json",
        }
        for hook_path in hook_paths.values():
            config = json.loads(hook_path.read_text(encoding="utf-8"))
            self.assertEqual(expected_events, set(config["hooks"]))
            for groups in config["hooks"].values():
                for group in groups:
                    for hook in group["hooks"]:
                        self.assertEqual(2, hook["timeout"])
        posix = (plugin_root / "bin" / "session-learning-hook").read_text(encoding="utf-8")
        windows = (plugin_root / "bin" / "session-learning-hook.cmd").read_text(encoding="utf-8")
        powershell = (plugin_root / "bin" / "session-learning-hook.ps1").read_text(
            encoding="utf-8"
        )
        javascript = (plugin_root / "bin" / "session-learning-hook.js").read_text(encoding="utf-8")
        for candidate in ("py", "python3", "python"):
            self.assertIn(candidate, posix)
            self.assertIn(candidate, windows + powershell)
            self.assertIn(candidate, javascript)
        self.assertIn("python-launcher", posix)
        self.assertIn("python-launcher", windows + powershell)
        self.assertIn("python-launcher", javascript)
        self.assertIn("session-learning-hook.ps1", windows)
        for launcher in (posix, powershell, javascript):
            self.assertIn("python_path", launcher)

        codex = json.loads(hook_paths["codex"].read_text(encoding="utf-8"))
        for groups in codex["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    self.assertNotIn("args", hook)
                    self.assertIn("commandWindows", hook)
        claude = json.loads(hook_paths["claude"].read_text(encoding="utf-8"))
        self.assertNotIn(
            "--warn-missing-python",
            claude["hooks"]["UserPromptSubmit"][0]["hooks"][0]["args"],
        )
        self.assertIn(
            "--warn-missing-python",
            claude["hooks"]["SessionStart"][0]["hooks"][0]["args"],
        )
        for groups in claude["hooks"].values():
            for group in groups:
                for hook in group["hooks"]:
                    self.assertEqual("node", hook["command"])
                    self.assertTrue(hook["args"][0].endswith("session-learning-hook.js"))

    @unittest.skipUnless(os.name == "nt", "Windows launcher behavior")
    def test_windows_launcher_warns_only_at_session_start_and_rejects_cached_commands(self) -> None:
        script = (
            REPO_ROOT
            / "plugins"
            / "mullans-productivity"
            / "bin"
            / "session-learning-hook.cmd"
        )
        payload = json.dumps(
            {
                "session_id": "launcher-test",
                "cwd": str(REPO_ROOT),
                "hook_event_name": "SessionStart",
                "source": "startup",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            sentinel = data_dir / "should-not-run"
            (data_dir / "python-launcher.txt").write_text(
                f'cmd /c type nul > "{sentinel}"', encoding="utf-8"
            )
            env = os.environ.copy()
            env["PATH"] = str(
                Path(env.get("COMSPEC", "C:/Windows/System32/cmd.exe")).parent
            )
            env["PLUGIN_DATA"] = str(data_dir)
            first = subprocess.run(
                [
                    env.get("COMSPEC", "cmd.exe"),
                    "/d",
                    "/c",
                    "call",
                    str(script),
                    "--warn-missing-python",
                    "--host",
                    "codex",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            second = subprocess.run(
                [
                    env.get("COMSPEC", "cmd.exe"),
                    "/d",
                    "/c",
                    "call",
                    str(script),
                    "--host",
                    "codex",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertIn("automatic retrieval is unavailable", first.stdout)
        self.assertEqual("", second.stdout.strip())
        self.assertFalse(sentinel.exists())

    @unittest.skipUnless(os.name == "nt", "Windows installed-layout smoke test")
    def test_windows_launcher_runs_from_installed_path_with_spaces(self) -> None:
        if not any(shutil.which(candidate) for candidate in ("py", "python3", "python")):
            self.skipTest("Python 3 launcher unavailable")
        source = REPO_ROOT / "plugins" / "mullans-productivity"
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            installed = temporary / "Installed Plugin With Spaces"
            shutil.copytree(source, installed)
            project = temporary / "project"
            lessons = project / ".agents" / "learning" / "lessons"
            lessons.mkdir(parents=True)
            record = v1_lesson()
            record.pop("destination")
            record["schema_version"] = 2
            record["delivery"] = {
                "mode": "dynamic",
                "host": None,
                "path": None,
                "instruction_path": "AGENTS.md",
                "enforcement_target": None,
            }
            (lessons / f"{record['id']}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )
            data_dir = temporary / "plugin data"
            env = os.environ.copy()
            env["PLUGIN_DATA"] = str(data_dir)
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            payload = json.dumps(
                {
                    "session_id": "installed-layout",
                    "cwd": str(project),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Update generated clients from the API schema",
                }
            )
            result = subprocess.run(
                [
                    env.get("COMSPEC", "cmd.exe"),
                    "/d",
                    "/c",
                    "call",
                    str(installed / "bin" / "session-learning-hook.cmd"),
                    "--host",
                    "codex",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        context = output["hookSpecificOutput"]["additionalContext"]
        self.assertIn("lesson.generated-files.001", context)

    def test_claude_node_dispatcher_emits_model_visible_context(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node launcher unavailable")
        if not any(shutil.which(candidate) for candidate in ("py", "python3", "python")):
            self.skipTest("Python 3 launcher unavailable")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            project = temporary / "project"
            lessons = project / ".agents" / "learning" / "lessons"
            lessons.mkdir(parents=True)
            record = v1_lesson()
            record.pop("destination")
            record["schema_version"] = 2
            record["delivery"] = {
                "mode": "dynamic",
                "host": None,
                "path": None,
                "instruction_path": "CLAUDE.md",
                "enforcement_target": None,
            }
            (lessons / f"{record['id']}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )
            env = os.environ.copy()
            env["CLAUDE_PLUGIN_DATA"] = str(temporary / "plugin data")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            payload = json.dumps(
                {
                    "session_id": "claude-dispatcher",
                    "cwd": str(project),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Update generated clients from the API schema",
                }
            )
            result = subprocess.run(
                [
                    node,
                    str(
                        REPO_ROOT
                        / "plugins"
                        / "mullans-productivity"
                        / "bin"
                        / "session-learning-hook.js"
                    ),
                    "--host",
                    "claude",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertIn(
            "lesson.generated-files.001",
            output["hookSpecificOutput"]["additionalContext"],
        )

    def test_claude_node_dispatcher_uses_project_configured_python_path(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node launcher unavailable")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            project = temporary / "project"
            self.seed_dynamic_project(project, instruction_path="CLAUDE.md")
            (project / ".agents" / "learning" / "config.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "python_path": str(Path(sys.executable).resolve()),
                    }
                ),
                encoding="utf-8",
            )
            empty_path = temporary / "empty-path"
            empty_path.mkdir()
            env = os.environ.copy()
            env["PATH"] = str(empty_path)
            env["CLAUDE_PLUGIN_DATA"] = str(temporary / "plugin data")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            payload = json.dumps(
                {
                    "session_id": "configured-claude-python",
                    "cwd": str(project),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Update generated clients from the API schema",
                }
            )

            result = subprocess.run(
                [
                    node,
                    str(
                        REPO_ROOT
                        / "plugins"
                        / "mullans-productivity"
                        / "bin"
                        / "session-learning-hook.js"
                    ),
                    "--host",
                    "claude",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                cwd=project,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        output = json.loads(result.stdout)
        self.assertIn(
            "lesson.generated-files.001",
            output["hookSpecificOutput"]["additionalContext"],
        )

    @unittest.skipUnless(os.name == "nt", "Windows configured launcher behavior")
    def test_windows_launcher_uses_project_configured_python_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            project = temporary / "prøject"
            self.seed_dynamic_project(project, instruction_path="AGENTS.md")
            (project / ".agents" / "learning" / "config.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "python_path": str(Path(sys.executable).resolve()),
                    }
                ),
                encoding="utf-8",
            )
            empty_path = temporary / "empty-path"
            empty_path.mkdir()
            env = os.environ.copy()
            env["PATH"] = str(empty_path)
            env["PLUGIN_DATA"] = str(temporary / "plugin data")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            payload = json.dumps(
                {
                    "session_id": "configured-codex-python",
                    "cwd": str(project),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Update generated clients from the API schema",
                }
            )
            launcher = (
                REPO_ROOT
                / "plugins"
                / "mullans-productivity"
                / "bin"
                / "session-learning-hook.cmd"
            )

            result = subprocess.run(
                [
                    env.get("COMSPEC", "C:/Windows/System32/cmd.exe"),
                    "/d",
                    "/c",
                    "call",
                    str(launcher),
                    "--host",
                    "codex",
                ],
                input=payload,
                text=True,
                capture_output=True,
                env=env,
                cwd=project,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), result.stderr)
        output = json.loads(result.stdout)
        self.assertIn(
            "lesson.generated-files.001",
            output["hookSpecificOutput"]["additionalContext"],
        )

    def test_codex_host_accepts_isolated_hook_configuration(self) -> None:
        codex = shutil.which("codex")
        if codex is None:
            self.skipTest("Codex CLI unavailable")
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            project = temporary / "project"
            lessons = project / ".agents" / "learning" / "lessons"
            lessons.mkdir(parents=True)
            record = v1_lesson()
            record.pop("destination")
            record["schema_version"] = 2
            record["delivery"] = {
                "mode": "dynamic",
                "host": None,
                "path": None,
                "instruction_path": "AGENTS.md",
                "enforcement_target": None,
            }
            (lessons / f"{record['id']}.json").write_text(
                json.dumps(record), encoding="utf-8"
            )
            launcher = (
                REPO_ROOT
                / "plugins"
                / "mullans-productivity"
                / "bin"
                / "session-learning-hook.cmd"
            )
            env = os.environ.copy()
            codex_home = temporary / "codex-home"
            codex_home.mkdir()
            (codex_home / "hooks.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "false",
                                            "commandWindows": f'\"{launcher}\" --host codex',
                                            "timeout": 2,
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            env["CODEX_HOME"] = str(codex_home)
            env["PLUGIN_DATA"] = str(temporary / "plugin-data")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run(
                [
                    codex,
                    "--dangerously-bypass-hook-trust",
                    "--enable",
                    "hooks",
                    "-C",
                    str(project),
                    "debug",
                    "prompt-input",
                    "Update generated clients from the API schema",
                ],
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("Update generated clients from the API schema", result.stdout)

    def test_runtime_skill_inventory_excludes_maintainer_files(self) -> None:
        skill = (
            REPO_ROOT
            / "plugins"
            / "mullans-productivity"
            / "skills"
            / "session-learning"
        )
        relative = {path.relative_to(skill).as_posix() for path in skill.rglob("*") if path.is_file()}
        self.assertFalse(any(path.startswith("tests/") for path in relative))
        self.assertNotIn("architecture.md", {Path(path).name for path in relative})

    def test_claude_marketplace_points_to_clean_shared_plugin_boundary(self) -> None:
        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(item for item in marketplace["plugins"] if item["name"] == "mullans-skills")
        self.assertEqual("./plugins/mullans-productivity", entry["source"])

        plugin_root = REPO_ROOT / "plugins" / "mullans-productivity"
        self.assertTrue((plugin_root / ".claude-plugin" / "plugin.json").is_file())
        self.assertFalse((REPO_ROOT / ".claude-plugin" / "plugin.json").exists())
        self.assertFalse((REPO_ROOT / "hooks").exists())
        self.assertFalse((REPO_ROOT / "bin").exists())
        for maintainer_directory in ("docs", "tests", "tools"):
            self.assertFalse((plugin_root / maintainer_directory).exists())

    def test_host_manifests_select_distinct_hook_configs(self) -> None:
        plugin_root = REPO_ROOT / "plugins" / "mullans-productivity"
        codex = json.loads(
            (plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (plugin_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual("./hooks/codex.json", codex["hooks"])
        self.assertEqual("./hooks/claude.json", claude["hooks"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual(
            {
                "./skills/brainstorm",
                "./skills/mark2word",
                "./skills/session-learning",
            },
            set(claude["skills"]),
        )
        self.assertFalse((plugin_root / "hooks" / "hooks.json").exists())

    def test_manifests_are_version_0_4_0(self) -> None:
        manifests = [
            REPO_ROOT
            / "plugins"
            / "mullans-productivity"
            / ".claude-plugin"
            / "plugin.json",
            REPO_ROOT / "plugins" / "mullans-productivity" / ".codex-plugin" / "plugin.json",
        ]
        for manifest in manifests:
            self.assertEqual("0.4.0", json.loads(manifest.read_text(encoding="utf-8"))["version"])

    def test_cli_exposes_v2_commands(self) -> None:
        help_stream = io.StringIO()
        previous = sys.stdout
        try:
            sys.stdout = help_stream
            with self.assertRaises(SystemExit) as raised:
                session_learning._build_parser().parse_args(["--help"])
        finally:
            sys.stdout = previous
        self.assertEqual(0, raised.exception.code)
        help_text = help_stream.getvalue()
        for command in (
            "apply-manifest",
            "activate",
            "migrate",
            "set-delivery",
            "deactivate",
            "reactivate",
            "reconcile-delivery",
            "hook",
        ):
            self.assertIn(command, help_text)


if __name__ == "__main__":
    unittest.main()
