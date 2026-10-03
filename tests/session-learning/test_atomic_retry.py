"""Script-owned, bounded Windows replacement retries preserve atomicity."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_session_learning_migrate import engine


class Clock:
    def __init__(self):
        self.now = 0.0
        self.delays = []

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        self.delays.append(delay)
        self.now += delay


def windows_error(code):
    error = PermissionError(13, 'injected Windows denial')
    error.winerror = code
    return error


class AtomicRetryTests(unittest.TestCase):
    def setUp(self):
        fixtures = Path(__file__).resolve().parents[2] / 'temp_windows_live_fixture'
        fixtures.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / '.session-learning/probe.json'
        self.target.parent.mkdir()
        self.target.write_bytes(b'original')
        self.clock = Clock()
        for owner, name, value in (
            (engine.sys, 'platform', 'win32'),
            (engine.time, 'monotonic', self.clock.monotonic),
            (engine.time, 'sleep', self.clock.sleep),
        ):
            patcher = mock.patch.object(owner, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_transient_errors_retry_same_completed_file(self):
        real_replace = engine.os.replace
        for code in (5, 32, 33):
            attempts = []
            def replace(source, target):
                attempts.append(source)
                self.assertEqual(b'new', Path(source).read_bytes())
                if len(attempts) <= 2:
                    raise windows_error(code)
                return real_replace(source, target)
            with self.subTest(code=code), mock.patch.object(engine.os, 'replace', side_effect=replace):
                engine._atomic_write_bytes(self.target, b'new')
                self.assertEqual(3, len(attempts))
                self.assertEqual(1, len(set(attempts)))
                self.assertEqual(b'new', self.target.read_bytes())
                self.assertFalse(list(self.target.parent.glob('*.tmp')))

    def test_persistent_denial_is_bounded_preserves_destination_and_error(self):
        failure = windows_error(5)
        with mock.patch.object(engine.os, 'replace', side_effect=failure) as replace:
            with self.assertRaisesRegex(PermissionError, 'atomic replacement.*failed after') as caught:
                engine._atomic_write_bytes(self.target, b'new')
        self.assertIs(failure, caught.exception)
        self.assertEqual(5, caught.exception.winerror)
        self.assertLessEqual(replace.call_count, 8)
        self.assertLessEqual(self.clock.now, 1.0)
        self.assertGreater(self.clock.now, 0)
        self.assertEqual(b'original', self.target.read_bytes())
        self.assertFalse(list(self.target.parent.glob('*.tmp')))

    def test_unrelated_errors_and_non_windows_do_not_retry(self):
        for platform, failure in [('win32', windows_error(112)), ('linux', windows_error(5))]:
            with self.subTest(platform=platform), mock.patch.object(engine.sys, 'platform', platform):
                with mock.patch.object(engine.os, 'replace', side_effect=failure) as replace:
                    with self.assertRaises(OSError):
                        engine._atomic_write_bytes(self.target, b'new')
                self.assertEqual(1, replace.call_count)
                self.assertEqual([], self.clock.delays)
                self.assertEqual(b'original', self.target.read_bytes())

    def test_attempt_limit_even_if_clock_does_not_advance(self):
        with mock.patch.object(engine.time, 'monotonic', return_value=0):
            with mock.patch.object(engine.os, 'replace', side_effect=windows_error(32)) as replace:
                with self.assertRaises(OSError):
                    engine._atomic_write_bytes(self.target, b'new')
        self.assertEqual(8, replace.call_count)

    def test_rollback_and_recovery_retry_transient_replacements(self):
        real_replace = engine.os.replace
        denied_once = set()
        def replace(source, target):
            content = Path(source).read_bytes()
            key = (str(target), content)
            if Path(target) == self.target and key not in denied_once:
                denied_once.add(key)
                raise windows_error(32)
            return real_replace(source, target)
        with mock.patch.object(engine.os, 'replace', side_effect=replace):
            with self.assertRaisesRegex(ValueError, 'validation failure'):
                engine.apply_file_transaction(self.root, {self.target: b'new'}, validator=lambda: ['validation failure'])
        self.assertEqual(b'original', self.target.read_bytes())
        self.assertEqual(2, len(denied_once))
        self.assertFalse((self.target.parent / '.transactions').exists())

        def fail_restore(source, target):
            if Path(target) == self.target and Path(source).read_bytes() == b'original':
                raise windows_error(5)
            return real_replace(source, target)
        with mock.patch.object(engine.os, 'replace', side_effect=fail_restore):
            with self.assertRaisesRegex(OSError, 'recovery journal retained'):
                engine.apply_file_transaction(self.root, {self.target: b'new'}, validator=lambda: ['validation failure'])
        transactions = self.target.parent / '.transactions'
        self.assertTrue(list(transactions.glob('*/journal.json')))
        denied_once.clear()
        with mock.patch.object(engine.os, 'replace', side_effect=replace):
            self.assertEqual(1, engine.recover_transactions(self.root))
        self.assertEqual(b'original', self.target.read_bytes())
        self.assertFalse(transactions.exists())
