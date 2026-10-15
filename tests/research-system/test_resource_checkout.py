"""Development regressions for the distributed cooperative checkout helper."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[2] / 'plugins/mullans-engineering/skills/research-setup/assets/resource-checkout/resource_lock.py'
spec = importlib.util.spec_from_file_location('packaged_checkout', path)
lock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lock)


class PackagedCheckoutTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        lock.init(self.root, dict(gpu='Device', dataset='Data', camera='Camera'))

    def claim(self, names, owner='a'):
        return lock.claim(self.root, owner, 'Fixture', names)['claim_id']

    def test_status_reports_complete_registered_set(self):
        identity = self.claim(['camera'])
        rows = {r['resource']: r for r in lock.status(self.root)['results']}
        self.assertEqual(set(rows), {'gpu', 'dataset', 'camera'})
        self.assertEqual(rows['camera']['claim_id'], identity)
        self.assertEqual(rows['gpu']['status'], 'available')

    def test_conflicts_report_all_requested_resources_atomically(self):
        gpu = self.claim(['gpu'], 'other')
        camera = self.claim(['camera'], 'third')
        before = (self.root / lock.LEDGER).read_bytes()
        with self.assertRaises(lock.LockError) as caught:
            self.claim(['gpu', 'dataset', 'camera'])
        rows = {r['resource']: r for r in caught.exception.result['results']}
        self.assertEqual(rows['gpu']['claim_id'], gpu)
        self.assertEqual(rows['camera']['claim_id'], camera)
        self.assertEqual(rows['dataset']['status'], 'available_not_acquired')
        self.assertEqual((self.root / lock.LEDGER).read_bytes(), before)

    def test_batch_release_partial_success_preserves_foreign_claims(self):
        own = self.claim(['gpu'])
        foreign = self.claim(['camera'], 'other')
        with patch.object(lock, 'write', wraps=lock.write) as writer:
            result = lock.release(self.root, 'a', [own, foreign])
        self.assertFalse(result['ok'])
        self.assertEqual(writer.call_count, 1)
        self.assertEqual([r['status'] for r in result['results']], ['released', 'ownership_mismatch'])
        self.assertEqual(lock.read(self.root)['claims'][0]['claim_id'], foreign)

    def test_selected_resources_and_batch_assertion(self):
        first = self.claim(['gpu', 'dataset'])
        second = self.claim(['camera'])
        lock.verify_many(self.root, 'a', [first, second], ['gpu', 'camera'])
        result = lock.release(self.root, 'a', [first, second], resources=['dataset', 'camera'])
        self.assertTrue(result['ok'])
        self.assertEqual(lock.read(self.root)['claims'][0]['resources'], ['gpu'])
        lock.verify(self.root, 'a', first, ['gpu'])

    def test_absent_identity_never_releases_replacement(self):
        previous = self.claim(['gpu'])
        lock.release(self.root, 'a', previous)
        replacement = self.claim(['gpu'])
        result = lock.release(self.root, 'a', previous, resources=['gpu'])
        self.assertFalse(result['ok'])
        self.assertEqual(result['results'][0]['status'], 'ownership_mismatch')
        self.assertEqual(lock.read(self.root)['claims'][0]['claim_id'], replacement)
        self.assertTrue(lock.release(self.root, 'a', previous)['ok'])

    def test_write_failure_reports_retained_claim(self):
        identity = self.claim(['gpu'])
        with patch.object(lock, 'write', side_effect=OSError('write failed')):
            result = lock.release(self.root, 'a', identity)
        self.assertFalse(result['ok'])
        self.assertEqual(result['results'][0]['status'], 'update_failure')
        lock.verify(self.root, 'a', identity, ['gpu'])

    def test_post_write_error_reports_confirmed_removal_but_failure(self):
        identity = self.claim(['gpu'])
        write = lock.write
        def fail_after_write(*args):
            write(*args)
            raise OSError('post-write failure')
        with patch.object(lock, 'write', side_effect=fail_after_write):
            result = lock.release(self.root, 'a', identity)
        self.assertFalse(result['ok'])
        self.assertEqual(result['results'][0]['status'], 'released')
        self.assertEqual(lock.read(self.root)['claims'], [])

    def test_confirmation_failure_never_reports_success(self):
        identity = self.claim(['gpu'])
        state = lock.read(self.root)
        with patch.object(lock, 'read', side_effect=[state, lock.LockError('reread failed')]):
            result = lock.release(self.root, 'a', identity)
        self.assertFalse(result['ok'])
        self.assertEqual(result['results'][0]['status'], 'confirmation_failure')

    def test_confirmation_and_update_share_guard(self):
        identity = self.claim(['gpu'])
        read = lock.read
        def guarded_read(*args):
            self.assertTrue((self.root / lock.GUARD).is_dir())
            return read(*args)
        with patch.object(lock, 'read', side_effect=guarded_read) as reader:
            self.assertTrue(lock.release(self.root, 'a', identity)['ok'])
        self.assertEqual(reader.call_count, 2)

    def test_evidence_is_never_inspected(self):
        for evidence in (None, self.root / 'missing', self.root / 'bad.json'):
            if evidence is not None and evidence.name == 'bad.json':
                evidence.write_text('malformed {')
            identity = self.claim(['gpu'])
            # A sentinel also proves there is no filesystem access to this argument.
            with patch.object(Path, 'is_file', side_effect=PermissionError('inaccessible')):
                self.assertTrue(lock.release(self.root, 'a', identity, evidence)['ok'])


if __name__ == '__main__':
    unittest.main()
