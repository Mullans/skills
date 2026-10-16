"""Single project location, manual move, and recoverable atomic writes."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

from test_session_learning_migrate import migration, engine, lesson_v1, evidence_v1


class StorageLocationTests(unittest.TestCase):
    def setUp(self):
        fixtures = Path(__file__).resolve().parents[2] / 'temp_windows_live_fixture'
        fixtures.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.old = self.root / '.agents/learning'
        self.new = self.root / '.session-learning'
        for folder in ('lessons', 'evidence'):
            (self.new / folder).mkdir(parents=True)
        self.record = engine.upgrade_lesson_record(lesson_v1(), authority='project', host='codex')
        self.record['version'] = engine.SKILL_VERSION
        self.record['usage'].update(confirmations=7, eligible_sessions=9,
                                   last_eligible_at='2026-09-19T12:00:00Z',
                                   last_confirmed_at='2026-09-19T12:00:00Z')
        (self.new / 'lessons' / f"{self.record['id']}.json").write_text(json.dumps(self.record))
        ev = engine.upgrade_evidence_record(evidence_v1(), authority='project')
        (self.new / 'evidence' / f"{ev['id']}.json").write_text(json.dumps(ev))
        (self.root / 'AGENTS.md').write_text(engine._instruction_pointer_block())
        engine.rebuild_index(self.root)

    def snapshot(self, path):
        return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob('*') if p.is_file()}

    def test_manual_move_preserves_canonical_and_derived_bytes(self):
        before = self.snapshot(self.new)
        self.old.parent.mkdir()
        self.new.rename(self.old)
        self.old.rename(self.new)
        self.assertEqual(before, self.snapshot(self.new))
        self.assertEqual([], engine.validate_store(self.root))
        self.assertEqual(self.new, engine.store_path(self.root))
        self.assertFalse(self.old.exists())

    def test_old_store_is_not_read_and_new_authoring_is_independent(self):
        self.old.parent.mkdir()
        self.new.rename(self.old)
        before = self.snapshot(self.old)
        self.assertEqual([], engine.search_lessons(self.root, 'lesson schema', authority='project'))
        self.assertEqual(self.new, engine.store_path(self.root))
        result = engine.apply_manifest(self.root, {
            'manifest_schema_version': 2, 'origin': 'current_session', 'changes': [
                {'path': f".session-learning/evidence/{evidence_v1()['id']}.json", 'json': engine.upgrade_evidence_record(evidence_v1(), authority='project')},
                {'path': f".session-learning/lessons/{self.record['id']}.json", 'json': self.record},
            ],
        })
        self.assertTrue(result['changed'])
        self.assertEqual(before, self.snapshot(self.old))
        self.assertEqual([], engine.validate_store(self.root))

    def test_schema_migrator_ignores_old_only_store(self):
        self.old.parent.mkdir()
        self.new.rename(self.old)
        before = self.snapshot(self.old)
        self.assertFalse(migration.migrate_store(self.root, authority='project')['changed'])
        self.assertEqual(before, self.snapshot(self.old))
        self.assertFalse(self.new.exists())

    def test_mixed_store_uses_only_new_location(self):
        self.old.mkdir(parents=True)
        (self.old / 'config.json').write_text('invalid old config')
        (self.old / 'lessons').mkdir()
        (self.old / 'lessons/invalid.json').write_text('invalid old lesson')
        before = self.snapshot(self.old)
        self.assertEqual([], engine.validate_store(self.root))
        self.assertTrue(engine.search_lessons(self.root, 'lesson schema', authority='project'))
        engine.rebuild_index(self.root)
        self.assertEqual(before, self.snapshot(self.old))

    def test_atomic_catalog_validation_failure_restores_bytes(self):
        catalog = self.new / 'retrieval.json'
        before = self.snapshot(self.new)
        with self.assertRaises(ValueError):
            engine.apply_file_transaction(self.root, {catalog: b'bad'}, validator=lambda: engine.validate_store(self.root))
        self.assertEqual(before, self.snapshot(self.new))

    def test_permission_failure_restores_only_completed_replacements(self):
        first = self.new / 'a.json'
        denied = self.new / 'z.json'
        first.write_bytes(b'original')
        denied.write_bytes(b'untouched')
        original = engine._atomic_write_bytes
        attempts = []
        def fail(target, content):
            attempts.append(target)
            if target == denied:
                raise PermissionError('denied replacement')
            return original(target, content)
        with mock.patch.object(engine, '_atomic_write_bytes', side_effect=fail):
            with self.assertRaises(PermissionError):
                engine.apply_file_transaction(self.root, {first: b'new', denied: b'new'})
        self.assertEqual(b'original', first.read_bytes())
        self.assertEqual(b'untouched', denied.read_bytes())
        self.assertEqual(1, attempts.count(denied))
        self.assertFalse((self.new / '.transactions').exists())

    def test_failed_rollback_retains_recovery_evidence_and_retry_restores(self):
        first = self.new / 'a.json'
        denied = self.new / 'z.json'
        first.write_bytes(b'original')
        original = engine._atomic_write_bytes
        def fail(target, content):
            if target == denied or (target == first and content == b'original'):
                raise PermissionError('injected write denial')
            return original(target, content)
        with mock.patch.object(engine, '_atomic_write_bytes', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'recovery journal retained'):
                engine.apply_file_transaction(self.root, {first: b'new', denied: b'new'})
        transactions = self.new / '.transactions'
        self.assertEqual(1, len(list(transactions.glob('*/journal.json'))))
        self.assertTrue(list(transactions.glob('*/*.bak')))
        self.assertEqual(b'new', first.read_bytes())
        self.assertEqual(1, engine.recover_transactions(self.root))
        self.assertEqual(b'original', first.read_bytes())
        self.assertFalse(transactions.exists())

    def test_local_path_is_unchanged_and_project_scoped(self):
        home = self.root / 'isolated-home'
        local = engine.store_path(self.root, authority='local', home_dir=home)
        self.assertEqual(home / '.agents/learning/projects' / engine.project_key(self.root), local)
        self.assertNotEqual(local, engine.store_path(self.root / 'another-project', authority='local', home_dir=home))
        self.assertFalse(home.exists())

    def test_manifest_accepts_only_new_logical_learning_paths(self):
        target, folder = engine._manifest_target(self.root, self.new, '.session-learning/lessons/x.json', 'project')
        self.assertEqual(self.new / 'lessons/x.json', target)
        self.assertEqual('lessons', folder)
        for authority in ('project', 'local'):
            with self.assertRaisesRegex(ValueError, 'unsupported|only logical'):
                engine._manifest_target(self.root, self.new, '.agents/learning/lessons/x.json', authority)

    def test_codex_override_visibility_absent_empty_nonempty(self):
        lesson = dict(self.record)
        lesson['delivery'] = {'mode': 'static', 'host': 'codex', 'path': 'AGENTS.md'}
        (self.root / 'AGENTS.md').write_text(f"<!-- session-learning:{lesson['id']} -->\nRule\n")
        self.assertTrue(engine._static_visible(lesson, self.root, self.root, 'codex'))
        override = self.root / 'AGENTS.override.md'
        override.write_text('')
        self.assertTrue(engine._static_visible(lesson, self.root, self.root, 'codex'))
        override.write_text('# Effective override\n')
        self.assertFalse(engine._static_visible(lesson, self.root, self.root, 'codex'))
