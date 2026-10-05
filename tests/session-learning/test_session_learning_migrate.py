from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
SCRIPT_DIR = (
    REPO_ROOT
    / "plugins"
    / "mullans-productivity"
    / "skills"
    / "session-learning"
    / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "session_learning_migrate", SCRIPT_DIR / "session_learning_migrate.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load session_learning_migrate.py")
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)
engine = migration.engine


def evidence_v1() -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "evidence",
        "id": "evidence.schema-migration.001",
        "session_id": "session-schema-migration",
        "signal": "explicit_user_correction",
        "situation": "An old lesson store was opened by a newer skill.",
        "attempted_behavior": "The newer skill rejected the record.",
        "feedback": "Same-major releases must remain compatible.",
        "corrected_behavior": "Migrate records sequentially before use.",
        "outcome": "The current validator accepts the store.",
        "created_at": "2026-09-19T12:00:00Z",
    }


def lesson_v1(*, schema_version: int = 1) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "record_type": "lesson",
        "id": "lesson.schema-migration.001",
        "title": "Migrate old lessons",
        "statement": "Migrate older lesson schemas before reading or writing them.",
        "kind": "guardrail",
        "status": "active",
        "scope": {"type": "paths", "paths": ["plugins/**/skills/session-learning/**"]},
        "triggers": ["lesson schema", "skill upgrade"],
        "anti_pattern": ["rejecting a supported old schema"],
        "safe_path": ["run the bundled sequential migrator"],
        "exceptions": [],
        "destination": {
            "type": "instruction",
            "host": "codex",
            "path": "AGENTS.md",
        },
        "provenance": [
            {
                "evidence_id": "evidence.schema-migration.001",
                "signal": "explicit_user_correction",
            }
        ],
        "relationships": {"supersedes": [], "related": []},
        "usage": {
            "eligible_sessions": 0,
            "confirmations": 0,
            "violations": 0,
            "repeat_corrections": 0,
            "last_eligible_at": None,
            "last_confirmed_at": None,
            "last_violated_at": None,
        },
        "timestamps": {
            "created_at": "2026-09-19T12:00:00Z",
            "updated_at": "2026-09-19T12:00:00Z",
        },
    }


class SessionLearningMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / ".session-learning"
        (self.store / "lessons").mkdir(parents=True)
        (self.store / "evidence").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_records(self, lesson: dict[str, object]) -> tuple[Path, Path]:
        lesson_path = self.store / "lessons" / f"{lesson['id']}.json"
        evidence_path = self.store / "evidence" / "evidence.schema-migration.001.json"
        lesson_path.write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps(evidence_v1(), indent=2) + "\n", encoding="utf-8")
        return lesson_path, evidence_path

    def test_migrates_v1_to_current_schema_transactionally(self) -> None:
        lesson = lesson_v1()
        lesson_path, evidence_path = self.write_records(lesson)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.schema-migration.001 -->\n"
            "- Old projected lesson.\n",
            encoding="utf-8",
        )

        result = migration.migrate_store(
            self.root, authority="project", host="codex"
        )

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        migrated_evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertTrue(result["changed"])
        self.assertEqual(engine.LESSON_SCHEMA_VERSION, migrated["schema_version"])
        self.assertEqual(engine.SKILL_VERSION, migrated["version"])
        self.assertEqual("project", migrated["authority"])
        self.assertIsNone(migrated["equivalence_key"])
        self.assertEqual([], migrated["conflict_targets"])
        self.assertEqual("dynamic", migrated["delivery"]["mode"])
        self.assertNotIn("destination", migrated)
        self.assertEqual(engine.EVIDENCE_SCHEMA_VERSION, migrated_evidence["schema_version"])
        self.assertEqual("project", migrated_evidence["authority"])
        instructions = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("session-learning:lesson.schema-migration.001", instructions)
        self.assertIn("session-learning:index", instructions)
        self.assertTrue((self.store / "retrieval.json").is_file())
        self.assertEqual([], engine.validate_store(self.root))

    def test_migration_is_idempotent(self) -> None:
        lesson_path, _ = self.write_records(lesson_v1())
        (self.root / "AGENTS.md").write_text("# Project\n", encoding="utf-8")
        migration.migrate_store(self.root, authority="project", host="codex")
        before = lesson_path.read_bytes()

        result = migration.migrate_store(
            self.root, authority="project", host="codex"
        )

        self.assertFalse(result["changed"])
        self.assertEqual(before, lesson_path.read_bytes())

    def test_current_schema_release_changes_preserve_store_bytes_and_provenance(self) -> None:
        lesson = engine.upgrade_lesson_record(
            lesson_v1(), authority="project", host="codex"
        )
        lesson_path, evidence_path = self.write_records(lesson)
        current_evidence = evidence_v1()
        current_evidence.update({"schema_version": 2, "authority": "project"})
        evidence_path.write_text(
            json.dumps(current_evidence, indent=2) + "\n", encoding="utf-8"
        )
        (self.root / "AGENTS.md").write_text(engine._ensure_pointer("# Project\n"), encoding="utf-8")
        for prior_version in ("0.6.0", "0.6.2", "0.8.0", f"{engine.SKILL_VERSION}-rc.1", "0.9.0"):
            with self.subTest(prior_version=prior_version):
                lesson["version"] = prior_version
                lesson_path.write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
                engine.rebuild_index(self.root)
                before = {
                    path.relative_to(self.root): path.read_bytes()
                    for path in self.root.rglob("*") if path.is_file()
                }
                audit = engine.audit_store(self.root, authority="both", home_dir=self.root)
                self.assertEqual([], audit["validation_errors"])
                self.assertEqual([], audit["migration_candidates"])
                self.assertFalse(audit["migration_available"])
                context = engine.retrospective_context(self.root, "lesson schema", home_dir=self.root)
                self.assertTrue(context["can_author"])
                self.assertEqual(0, context["migration_candidates"]["total"])
                result = migration.migrate_store(
                    self.root, authority="both", home_dir=self.root, host="codex"
                )
                migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
                self.assertFalse(result["changed"])
                self.assertEqual(engine.LESSON_SCHEMA_VERSION, migrated["schema_version"])
                self.assertEqual(prior_version, migrated["version"])
                after = {
                    path.relative_to(self.root): path.read_bytes()
                    for path in self.root.rglob("*") if path.is_file()
                }
                self.assertEqual(before, after)

    def test_current_schema_local_lesson_requires_no_release_migration(self) -> None:
        lesson = engine.upgrade_lesson_record(
            lesson_v1(), authority="local", host="codex"
        )
        lesson["version"] = "0.8.0"
        local_store = engine.store_path(self.root, authority="local", home_dir=self.root)
        (local_store / "lessons").mkdir(parents=True)
        (local_store / "evidence").mkdir()
        lesson_path = local_store / "lessons" / f"{lesson['id']}.json"
        evidence_path = local_store / "evidence" / "evidence.schema-migration.001.json"
        lesson_path.write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
        current_evidence = evidence_v1()
        current_evidence.update({"schema_version": 2, "authority": "local"})
        evidence_path.write_text(
            json.dumps(current_evidence, indent=2) + "\n", encoding="utf-8"
        )

        engine.rebuild_index(self.root, authority="local", home_dir=self.root)
        before = {path: path.read_bytes() for path in local_store.rglob("*") if path.is_file()}
        audit = engine.audit_store(self.root, authority="both", home_dir=self.root)
        self.assertEqual([], audit["validation_errors"])
        self.assertEqual([], audit["migration_candidates"])
        result = migration.migrate_store(self.root, authority="both", home_dir=self.root)

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertFalse(result["changed"])
        self.assertEqual("0.8.0", migrated["version"])
        self.assertEqual(before, {path: path.read_bytes() for path in local_store.rglob("*") if path.is_file()})

    def test_invalid_current_writing_version_is_not_a_migration_candidate(self) -> None:
        lesson = engine.upgrade_lesson_record(lesson_v1(), authority="project")
        for writing_version in (None, "invalid", "1.0.0"):
            with self.subTest(writing_version=writing_version):
                lesson["version"] = writing_version
                lesson_path, evidence_path = self.write_records(lesson)
                before = (lesson_path.read_bytes(), evidence_path.read_bytes())
                context = engine.retrospective_context(self.root, "lesson schema", home_dir=self.root)
                self.assertFalse(context["can_author"])
                self.assertEqual(0, context["migration_candidates"]["total"])
                with self.assertRaises(ValueError):
                    migration.migrate_store(self.root, authority="project")
                self.assertEqual(before, (lesson_path.read_bytes(), evidence_path.read_bytes()))

    def test_current_schema_does_not_downgrade_a_newer_same_major_version(self) -> None:
        lesson = engine.upgrade_lesson_record(
            lesson_v1(), authority="project", host="codex"
        )
        lesson["version"] = "0.9.0"
        lesson_path, evidence_path = self.write_records(lesson)
        current_evidence = evidence_v1()
        current_evidence.update({"schema_version": 2, "authority": "project"})
        evidence_path.write_text(
            json.dumps(current_evidence, indent=2) + "\n", encoding="utf-8"
        )

        result = migration.migrate_store(
            self.root, authority="project", host="codex"
        )

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertFalse(result["changed"])
        self.assertEqual("0.9.0", migrated["version"])

    def test_evidence_schema_upgrade_preserves_current_lesson_writing_version(self) -> None:
        lesson = engine.upgrade_lesson_record(lesson_v1(), authority="project")
        lesson["version"] = "0.6.2"
        lesson_path, evidence_path = self.write_records(lesson)
        (self.root / "AGENTS.md").write_text(engine._ensure_pointer("# Project\n"), encoding="utf-8")
        engine.rebuild_index(self.root)
        before_lesson = lesson_path.read_bytes()

        result = migration.migrate_store(self.root, authority="project")

        self.assertTrue(result["changed"])
        self.assertEqual([], result["authorities"][0]["lessons"])
        self.assertEqual([".session-learning/evidence/evidence.schema-migration.001.json"], result["authorities"][0]["files"])
        self.assertEqual(before_lesson, lesson_path.read_bytes())
        self.assertEqual(engine.EVIDENCE_SCHEMA_VERSION, json.loads(evidence_path.read_text(encoding="utf-8"))["schema_version"])
        self.assertEqual([], engine.validate_store(self.root))

    def test_migrates_v2_metadata_without_changing_delivery(self) -> None:
        lesson = lesson_v1(schema_version=2)
        lesson.pop("destination")
        lesson["delivery"] = {
            "mode": "static",
            "host": "codex",
            "path": "AGENTS.md",
            "instruction_path": None,
            "enforcement_target": None,
        }
        lesson_path, _ = self.write_records(lesson)
        (self.root / "AGENTS.md").write_text(
            "<!-- session-learning:lesson.schema-migration.001 -->\n"
            "- Migrate older lesson schemas before reading or writing them.\n",
            encoding="utf-8",
        )

        migration.migrate_store(self.root, authority="project", host="codex")

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertEqual("static", migrated["delivery"]["mode"])
        self.assertEqual("project", migrated["authority"])
        self.assertEqual([], engine.validate_store(self.root))

    def test_local_migration_does_not_touch_project_projection(self) -> None:
        home = self.root / "home"
        local_store = engine.store_path(
            self.root, authority="local", home_dir=home
        )
        (local_store / "lessons").mkdir(parents=True)
        (local_store / "evidence").mkdir()
        lesson = lesson_v1()
        lesson_path = local_store / "lessons" / f"{lesson['id']}.json"
        evidence_path = (
            local_store / "evidence" / "evidence.schema-migration.001.json"
        )
        lesson_path.write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
        evidence_path.write_text(
            json.dumps(evidence_v1(), indent=2) + "\n", encoding="utf-8"
        )
        instructions = self.root / "AGENTS.md"
        original = (
            "<!-- session-learning:lesson.schema-migration.001 -->\n- Project rule.\n"
        )
        instructions.write_text(original, encoding="utf-8")

        result = migration.migrate_store(
            self.root,
            authority="local",
            home_dir=home,
            host="codex",
        )

        migrated = json.loads(lesson_path.read_text(encoding="utf-8"))
        self.assertTrue(result["changed"])
        self.assertEqual("local", migrated["authority"])
        self.assertEqual(original, instructions.read_text(encoding="utf-8"))
        self.assertEqual(
            [], engine.validate_store(self.root, authority="local", home_dir=home)
        )

    def test_newer_schema_fails_without_modifying_store(self) -> None:
        lesson_path, evidence_path = self.write_records(lesson_v1(schema_version=999))
        before_lesson = lesson_path.read_bytes()
        before_evidence = evidence_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "newer than supported"):
            migration.migrate_store(self.root, authority="project", host="codex")

        self.assertEqual(before_lesson, lesson_path.read_bytes())
        self.assertEqual(before_evidence, evidence_path.read_bytes())

    def test_validation_failure_rolls_back_every_migrated_file(self) -> None:
        lesson = lesson_v1()
        lesson.pop("title")
        lesson_path, evidence_path = self.write_records(lesson)
        instructions = self.root / "AGENTS.md"
        instructions.write_text(
            "<!-- session-learning:lesson.schema-migration.001 -->\n"
            "- Old projected lesson.\n",
            encoding="utf-8",
        )
        before = {
            lesson_path: lesson_path.read_bytes(),
            evidence_path: evidence_path.read_bytes(),
            instructions: instructions.read_bytes(),
        }

        with self.assertRaisesRegex(ValueError, "missing required field 'title'"):
            migration.migrate_store(self.root, authority="project", host="codex")

        for path, content in before.items():
            self.assertEqual(content, path.read_bytes())
        self.assertFalse((self.store / "index.md").exists())
        self.assertFalse((self.store / "retrieval.json").exists())


if __name__ == "__main__":
    unittest.main()
