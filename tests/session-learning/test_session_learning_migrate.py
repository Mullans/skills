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
        self.store = self.root / ".agents" / "learning"
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

    def test_current_schema_migration_updates_the_writing_skill_version(self) -> None:
        lesson = engine.upgrade_lesson_record(
            lesson_v1(), authority="project", host="codex"
        )
        lesson["version"] = "0.6.0"
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
        self.assertTrue(result["changed"])
        self.assertEqual(engine.LESSON_SCHEMA_VERSION, migrated["schema_version"])
        self.assertEqual(engine.SKILL_VERSION, migrated["version"])

    def test_current_schema_does_not_downgrade_a_newer_same_major_version(self) -> None:
        lesson = engine.upgrade_lesson_record(
            lesson_v1(), authority="project", host="codex"
        )
        lesson["version"] = "0.7.0"
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
        self.assertEqual("0.7.0", migrated["version"])

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
