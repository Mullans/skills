"""Disposable checks only: never opens a project's live ledger or resources."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import resource_lock as lock


class ResourceLockTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        lock.init(self.root, {"gpu": "Exclusive accelerator", "dataset": "Mutable working dataset"})
        self.receipt = self.root / "final-state.txt"
        self.receipt.write_text("Task stopped; final state verified", encoding="utf-8")

    def take(self, owner="session-a", resources=("gpu",)):
        return lock.claim(self.root, owner, "Disposable test", resources)

    def assert_blocked_unchanged(self, operation):
        before = (self.root / lock.LEDGER).read_bytes()
        with self.assertRaises(lock.LockError):
            operation()
        self.assertEqual((self.root / lock.LEDGER).read_bytes(), before)

    def test_init_refuses_existing_ledger(self):
        self.take()
        self.assert_blocked_unchanged(lambda: lock.init(self.root, {"other": "Different scope"}))

    def test_missing_ledger_is_not_treated_as_available(self):
        (self.root / lock.LEDGER).unlink()
        with self.assertRaises(lock.LockError):
            lock.status(self.root)
        with self.assertRaises(lock.LockError):
            self.take()
        self.assertFalse((self.root / lock.LEDGER).exists())

    def test_corrupt_ledger_blocks_operations(self):
        for content in ("broken", "<!-- resource-lock-json\n{}\n-->\n"):
            (self.root / lock.LEDGER).write_text(content, encoding="utf-8")
            for op in (lambda: lock.status(self.root), self.take,
                       lambda: lock.release(self.root, "a", "b", self.receipt)):
                self.assert_blocked_unchanged(op)

    def test_old_project_schema_is_not_migrated(self):
        (self.root / lock.LEDGER).write_text(
            '<!-- resource-lock-json\n{"version":1,"claims":[]}\n-->\n', encoding="utf-8")
        self.assert_blocked_unchanged(self.take)
        self.assert_blocked_unchanged(lambda: lock.init(self.root, {"gpu": "GPU"}))

    def test_duplicate_json_keys_rejected(self):
        text = (self.root / lock.LEDGER).read_text()
        text = text.replace('"version": 2', '"version": 2, "version": 2')
        (self.root / lock.LEDGER).write_text(text)
        self.assert_blocked_unchanged(self.take)

    def test_overlapping_claims_rejected(self):
        item = self.take()
        state = lock.status(self.root)
        duplicate = dict(item, claim_id=str(lock.uuid4()))
        state["claims"].append(duplicate)
        text = lock.START + json.dumps(state) + lock.END
        (self.root / lock.LEDGER).write_text(text)
        self.assert_blocked_unchanged(lambda: lock.status(self.root))

    def test_identity_and_scope_verification(self):
        item = self.take()
        self.assertEqual(lock.verify(self.root, "session-a", item["claim_id"], ("gpu",)), item)
        for owner, claim_id, resources in (
            ("session-b", item["claim_id"], ("gpu",)),
            ("session-a", str(lock.uuid4()), ("gpu",)),
            ("session-a", item["claim_id"], ("dataset",)),
            ("session-a", item["claim_id"], ("gpu", "dataset")),
        ):
            self.assert_blocked_unchanged(
                lambda: lock.verify(self.root, owner, claim_id, resources))

    def test_bundle_conflict_has_no_partial_acquisition(self):
        item = self.take("dataset-session", ("dataset",))
        self.assert_blocked_unchanged(lambda: self.take(resources=("gpu", "dataset")))
        self.assertEqual(lock.status(self.root)["claims"], [item])

    def test_independent_resources_and_bundled_release(self):
        first = self.take()
        second = self.take("session-b", ("dataset",))
        lock.release(self.root, "session-a", first["claim_id"], self.receipt)
        self.assertEqual(lock.status(self.root)["claims"], [second])
        lock.release(self.root, "session-b", second["claim_id"], self.receipt)
        both = self.take(resources=("gpu", "dataset"))
        lock.verify(self.root, "session-a", both["claim_id"], ("gpu", "dataset"))
        lock.release(self.root, "session-a", both["claim_id"], self.receipt)
        self.assertEqual(lock.status(self.root)["claims"], [])

    def test_release_requires_identity_and_nonempty_receipt(self):
        item = self.take()
        empty = self.root / "empty.txt"
        empty.touch()
        for owner, claim_id, evidence in (
            ("session-b", item["claim_id"], self.receipt),
            ("session-a", str(lock.uuid4()), self.receipt),
            ("session-a", item["claim_id"], self.root / "missing"),
            ("session-a", item["claim_id"], empty),
            ("session-a", item["claim_id"], self.root),
        ):
            self.assert_blocked_unchanged(
                lambda: lock.release(self.root, owner, claim_id, evidence))

    def test_abandoned_guard_blocks_reads_and_writes(self):
        guard = self.root / lock.GUARD
        guard.mkdir()
        with patch.object(lock, "GUARD_WAIT", 0):
            for op in (lambda: lock.status(self.root), self.take,
                       lambda: lock.refresh(self.root)):
                self.assert_blocked_unchanged(op)
        self.assertTrue(guard.is_dir())

    def test_age_does_not_expire_claim(self):
        item = self.take()
        state = lock.status(self.root)
        state["claims"][0]["claimed_at"] = "2000-01-01T00:00:00+00:00"
        with lock.guard(self.root):
            lock.write(self.root, state)
        self.assert_blocked_unchanged(lambda: self.take("other"))
        lock.verify(self.root, "session-a", item["claim_id"], ("gpu",))

    def test_replace_failure_preserves_ledger_and_cleans_own_guard(self):
        before = (self.root / lock.LEDGER).read_bytes()
        with patch.object(lock.os, "replace", side_effect=OSError("Injected failure")):
            with self.assertRaises(OSError):
                self.take()
        self.assertEqual((self.root / lock.LEDGER).read_bytes(), before)
        self.assertFalse((self.root / lock.GUARD).exists())
        self.assertEqual(list(self.root.glob(".resource_lock-*.tmp")), [])

    def test_refresh_preserves_claim_identity(self):
        item = self.take()
        lock.refresh(self.root)
        self.assertEqual(lock.status(self.root)["claims"], [item])

    def test_unknown_or_duplicate_resources_rejected(self):
        for resources in ((), ("unknown",), ("gpu", "gpu")):
            self.assert_blocked_unchanged(lambda: self.take(resources=resources))

    def test_processes_from_different_directories_have_one_winner(self):
        processes = []
        script = str(Path(lock.__file__).resolve())
        for name in ("one", "two"):
            cwd = self.root / name
            cwd.mkdir()
            processes.append(subprocess.Popen(
                [sys.executable, "-B", script, "--state-dir", str(self.root), "claim",
                 "--resource", "gpu", "--owner", name, "--reason", "Concurrency test"],
                cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        try:
            outputs = [p.communicate(timeout=15) for p in processes]
            self.assertEqual(sorted(p.returncode for p in processes), [0, 2], outputs)
            # Claim survives the successful process exiting.
            state = lock.status(self.root)
            self.assertEqual(len(state["claims"]), 1)
            winner = next(json.loads(out) for p, (out, err) in zip(processes, outputs)
                          if p.returncode == 0)
            self.assertEqual(state["claims"], [winner])
        finally:
            for p in processes:
                if p.poll() is None:
                    p.kill()
                p.wait()

    def test_cli_init_verify_and_release(self):
        authority = self.root / "another-authority"
        authority.mkdir()
        script = str(Path(lock.__file__).resolve())

        def run(*args):
            return subprocess.run(
                [sys.executable, "-B", script, "--state-dir", str(authority), *args],
                capture_output=True, text=True, timeout=15)

        self.assertEqual(run("init", "--resource", "gpu=Accelerator").returncode, 0)
        result = run("claim", "--resource", "gpu", "--owner", "cli-session", "--reason", "Test")
        self.assertEqual(result.returncode, 0, result.stderr)
        item = json.loads(result.stdout)
        self.assertEqual(run("verify", "--resource", "gpu", "--owner", "cli-session",
                             "--claim-id", item["claim_id"]).returncode, 0)
        self.assertEqual(run("release", "--owner", "cli-session", "--claim-id", item["claim_id"],
                             "--evidence", str(self.receipt)).returncode, 0)
        self.assertEqual(json.loads(run("status").stdout)["claims"], [])

    def test_invalid_resource_definition_is_rejected_without_ledger(self):
        authority = self.root / "invalid-init"
        authority.mkdir()
        result = subprocess.run(
            [sys.executable, "-B", str(Path(lock.__file__).resolve()), "--state-dir", str(authority),
             "init", "--resource", "gpu=One", "--resource", "gpu=Two"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertFalse((authority / lock.LEDGER).exists())


if __name__ == "__main__":
    unittest.main()
