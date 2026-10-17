"""Synthetic, portable artifact lifecycle checks; no project data or live tools."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

ASSET = Path(__file__).resolve().parents[2] / 'plugins/mullans-engineering/skills/research-setup/assets/artifact-system/scripts/workspace/artifact_workspace.py'
spec = importlib.util.spec_from_file_location('artifact_workspace_asset', ASSET)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArtifactWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.store = module.Store(self.project)
        self.addCleanup(self.store.close)
        self.first = Path(self.store.begin('one')['root'])
        self.second = Path(self.store.begin('two')['root'])

    def file(self, root, name='analysis/data.bin', content=b'evidence'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def finish(self, root, **kwargs):
        return self.store.finish(root, 'Results assessed', writers_closed=True, apply=True, **kwargs)

    def test_ownership_is_required_before_command_or_payload(self):
        output = self.project / 'local/unowned/output'
        with patch.object(module.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Register'):
                self.store.run(output, ['tool'])
            run.assert_not_called()
        self.assertFalse(output.exists())

    def test_closeout_cleans_owned_files_and_reports_closed_root_exceptions(self):
        path = self.file(self.first)
        self.store.reconcile()
        self.assertFalse(self.store.cleanup()['candidates'])
        self.finish(self.first)
        self.assertFalse(path.exists())
        late = self.file(self.first, 'scratch/late.bin')
        result = self.store.cleanup(apply=True)
        self.assertIn(str(late), result['unclassified'])
        self.assertTrue(late.exists())

    def test_failed_command_enrolls_partials_and_private_rebuild_is_allowed(self):
        output = self.first / 'builds/test'
        def fail(*args, **kwargs):
            self.file(output, 'partial.obj')
            raise subprocess.CalledProcessError(1, 'synthetic')
        with patch.object(module.subprocess, 'run', side_effect=fail):
            with self.assertRaises(subprocess.CalledProcessError):
                self.store.run(self.first, ['tool'], output=output)
        self.assertIsNotNone(self.store.db.execute('SELECT path FROM files WHERE path=?',
                                                   (str(output/'partial.obj'),)).fetchone())
        with patch.object(module.subprocess, 'run'):
            self.store.run(self.first, ['tool'], output=output)
        self.finish(self.first)
        self.assertFalse((output/'partial.obj').exists())

    def test_shared_input_survives_until_last_consumer_finishes(self):
        source = self.file(self.first)
        self.store.claim('two:main', self.store.manifest([source]))
        self.finish(self.first)
        self.assertTrue(source.exists())
        self.finish(self.second)
        self.assertFalse(source.exists())

    def test_preservation_and_pool_expiry(self):
        source = self.file(self.first)
        self.store.keep([source], 'Canonical source with regular reuse')
        pooled = self.file(self.first, 'analysis/pooled.bin')
        self.store.keep([pooled], 'Expected parser comparison', days=7)
        self.finish(self.first)
        self.assertTrue(source.exists())
        self.assertTrue(pooled.exists())
        clock = module.utc()
        with patch.object(module, 'utc', return_value=clock+timedelta(days=8)):
            self.store.cleanup(apply=True)
        self.assertTrue(source.exists())
        self.assertFalse(pooled.exists())

    def test_recovery_proof_and_writer_assessment_gate_closeout(self):
        journal = self.file(self.first, 'backups/journal.json')
        self.store.recover(self.first, journal)
        with self.assertRaisesRegex(ValueError, 'recovery'):
            self.finish(self.first)
        proof = self.file(self.first, 'backups/proof.json', b'operation-specific verified recovery')
        self.store.recover(self.first, journal, proof)
        self.store.db.execute("INSERT INTO jobs VALUES ('held','one:main','running',NULL)")
        with self.assertRaisesRegex(ValueError, 'writer'):
            self.finish(self.first)
        self.store.db.execute("UPDATE jobs SET state='assessed' WHERE id='held'")
        proof.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'recovery'):
            self.finish(self.first)

    def recipe(self):
        implementation = self.project/'generator.py'
        implementation.write_text('# synthetic generator')
        recipe = self.project/'recipe.json'
        recipe.write_text(json.dumps(dict(operation='candidate', implementation=['generator.py'],
            settings={'level':6}, retain=['candidate.bin'], candidate=True)))
        return recipe

    def test_recipe_reuses_verified_result_and_candidate_verification_is_fresh(self):
        source = self.file(self.first)
        recipe = self.recipe()
        output = self.first/'builds/candidate'
        def generate(command, **kwargs):
            if command[0] == 'generate':
                self.file(Path(command[2]), 'candidate.bin')
        with patch.object(module.subprocess, 'run', side_effect=generate) as run:
            result = self.store.run(self.first, ['generate',str(source),str(output)], [source],
                                    output, recipe, ['verify',str(output)])
            self.assertFalse(result['reused'])
            self.assertEqual(run.call_count, 2)
            other = self.second/'builds/candidate'
            reused = self.store.run(self.second, ['generate',str(source),str(other)], [source],
                                    other, recipe, ['verify',str(other)])
            self.assertTrue(reused['reused'])
            self.assertEqual(run.call_count, 2)
            self.assertEqual(self.store.resolve(self.second, other), output)
            equivalent = self.file(self.second,'samples/same-content.bin')
            duplicate = self.second/'builds/equivalent'
            result = self.store.run(self.second,['generate',str(equivalent),str(duplicate)], [equivalent],
                                    duplicate, recipe, ['verify',str(duplicate)])
            self.assertTrue(result['reused'])
            self.assertEqual(run.call_count,2)
            source.write_bytes(b'new input')
            changed = self.second/'builds/changed'
            result = self.store.run(self.second, ['generate',str(source),str(changed)], [source],
                                    changed, recipe, ['verify',str(changed)])
            self.assertFalse(result['reused'])
            self.assertEqual(run.call_count, 4)

    def test_recipe_rejects_missing_verification_and_does_not_cache_failed_verification(self):
        recipe = self.recipe()
        output = self.first/'builds/candidate'
        with self.assertRaisesRegex(ValueError, 'independent verification'):
            self.store.run(self.first, ['generate'], output=output, recipe=recipe)
        with patch.object(module.subprocess, 'run', side_effect=[None,
                subprocess.CalledProcessError(1, 'verification')]):
            with self.assertRaises(subprocess.CalledProcessError):
                self.store.run(self.first, ['generate'], output=output, recipe=recipe, verify=['verify'])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM recipes').fetchone()[0], 0)

    def test_changed_retained_result_and_concurrent_recipe_never_reuse(self):
        recipe = self.recipe()
        output = self.first/'builds/candidate'
        def generate(*args, **kwargs):
            self.file(output, 'candidate.bin')
        with patch.object(module.subprocess, 'run', side_effect=generate):
            self.store.run(self.first, ['generate'], output=output, recipe=recipe, verify=['verify'])
        (output/'candidate.bin').write_bytes(b'changed')
        key = self.store.db.execute('SELECT key FROM recipes').fetchone()[0]
        self.store.db.execute("INSERT INTO jobs VALUES ('held','one:main','running',?)", (key,))
        with patch.object(module.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'same recipe'):
                self.store.run(self.second, ['generate'], output=self.second/'builds/new',
                               recipe=recipe, verify=['verify'])
            run.assert_not_called()

    def test_completed_experiment_cannot_reopen_through_a_new_test(self):
        self.finish(self.first, experiment=True)
        with self.assertRaisesRegex(ValueError, 'new experiment identity'):
            self.store.begin('one', test='next', root=self.first/'analysis/next')

    def test_experiment_closeout_accepts_previously_assessed_recovery_and_finished_tests(self):
        journal=self.file(self.first,'backups/journal.json')
        proof=self.file(self.first,'backups/proof.json',b'verified restoration')
        self.store.recover(self.first,journal,proof)
        next_root=self.first/'analysis/next'
        self.store.begin('one',test='next',root=next_root)
        self.finish(self.first)
        self.assertFalse(proof.exists())
        self.finish(next_root,experiment=True)
        with self.assertRaisesRegex(ValueError,'new experiment identity'):
            self.store.begin('one',test='later',root=self.first/'later')
        self.finish(next_root,experiment=True)

    def test_all_finished_tests_still_allow_final_experiment_closeout(self):
        self.finish(self.first)
        self.finish(self.first,experiment=True)
        with self.assertRaisesRegex(ValueError,'new experiment identity'):
            self.store.begin('one',test='later',root=self.first/'later')

    def test_partial_retirement_failure_leaves_durable_receipt(self):
        first=self.file(self.first,'analysis/a.bin')
        second=self.file(self.first,'analysis/b.bin')
        self.store.finish(self.first,'assessed',writers_closed=True)
        verify=self.store.verify
        def changed(rows):
            if rows[0]['path']==str(second):
                raise ValueError('second changed')
            return verify(rows)
        with patch.object(self.store,'verify',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'second changed'):
                with self.store.locked():
                    self.store.cleanup(apply=True)
        self.assertFalse(first.exists())
        self.assertTrue(second.exists())
        receipt=self.project/'local/artifacts/retirement.jsonl'
        self.assertIn(str(first),json.loads(receipt.read_text().splitlines()[0])['path'])

    def test_unregistered_experiment_directory_is_reported(self):
        orphan=self.project/'local/experiments/unregistered'
        orphan.mkdir()
        (orphan/'data').write_bytes(b'data')
        result=self.store.cleanup(apply=True)
        self.assertIn(str(orphan),result['unclassified'])
        self.assertTrue((orphan/'data').exists())

    def test_linked_paths_and_nonempty_adoption_are_rejected(self):
        historical = self.project/'local/experiments/old'
        historical.mkdir(parents=True)
        (historical/'evidence').write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'historical'):
            self.store.begin('old')
        with self.assertRaises(ValueError):
            self.store.path(self.project/'outside')


if __name__ == '__main__':
    unittest.main()
