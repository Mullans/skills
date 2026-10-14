"""Handoff note insertion tests; use disposable files, never real handoffs."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins/mullans-engineering/skills/research-handoff/scripts/add_handoff_note.py"
spec = importlib.util.spec_from_file_location("handoff_notes", SCRIPT)
notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notes)


class HandoffNoteTests(unittest.TestCase):
    def setUp(self):
        fixture_root = ROOT / "temp_windows_live_fixture" / "handoff-notes"
        fixture_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixture_root)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "handoff.md"
        self.original = b"# Handoff\n\nCore plan, status and ownership remain here.\n"
        self.path.write_bytes(self.original)
        self.note = notes.render_note("agent", "Free Cam", "Expose timed holds.", "2026-10-14")

    def run_cli(self, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.path), "--request-type", "agent",
             "--source", "Free Cam", "--request", "Expose timed holds.", "--date", "2026-10-14", *extra],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_new_section_preserves_original_bytes(self):
        run = self.run_cli()
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual("added", json.loads(run.stdout)["status"])
        self.assertEqual(self.original + ("\n## Handoff notes\n\n" + self.note + "\n").encode(), self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_existing_section_preserves_later_sections(self):
        original = self.original + b"\n## Handoff notes\n\n- Existing free-form request.\n\n## References\n\nKeep this unchanged.\n"
        self.path.write_bytes(original)
        notes.add_note(self.path, self.note)
        result = self.path.read_bytes()
        self.assertTrue(result.startswith(self.original))
        self.assertIn(b"- Existing free-form request.\n", result)
        self.assertTrue(result.endswith(b"## References\n\nKeep this unchanged.\n"))
        self.assertEqual(1, result.count(b"## Handoff notes"))

    def test_duplicate_ignores_date_and_context_without_rewriting(self):
        notes.add_note(self.path, self.note)
        before = self.path.read_bytes()
        repeated = notes.render_note("agent", "free cam", "Expose timed holds.", "2026-10-15", "../experiment.md")
        self.assertEqual("already-present", notes.add_note(self.path, repeated)["status"])
        self.assertEqual(before, self.path.read_bytes())
        user = notes.render_note("user", "Free Cam", "Expose timed holds.", "2026-10-15")
        self.assertEqual("added", notes.add_note(self.path, user)["status"])

    def test_crlf_bom_and_missing_final_newline_are_preserved(self):
        for original in (b"\xef\xbb\xbf# Core\r\n\r\nBody\r\n", b"# Core without final newline"):
            with self.subTest(original=original):
                self.path.write_bytes(original)
                notes.add_note(self.path, self.note)
                result = self.path.read_bytes()
                self.assertTrue(result.startswith(original))
                if b"\r\n" in original:
                    self.assertNotIn(b"\n", result.replace(b"\r\n", b""))

    def test_dry_run_never_writes_or_locks(self):
        run = self.run_cli("--dry-run")
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertTrue(json.loads(run.stdout)["dry_run"])
        self.assertEqual(self.original, self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_parallel_distinct_and_duplicate_additions(self):
        requests = ["Hold W.", "Hold O.", "Hold K.", "Hold W.", "Hold O."]
        processes = [
            subprocess.Popen(
                [sys.executable, str(SCRIPT), str(self.path), "--request-type", "agent",
                 "--source", "Free Cam", "--request", request, "--date", "2026-10-14"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            for request in requests
        ]
        statuses = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(0, process.returncode, stderr)
            statuses.append(json.loads(stdout)["status"])
        self.assertEqual(3, statuses.count("added"))
        self.assertEqual(2, statuses.count("already-present"))
        content = self.path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith(self.original.decode()))
        self.assertEqual(1, content.count("## Handoff notes"))
        for request in set(requests):
            self.assertEqual(1, content.count(request))
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_busy_lock_is_not_stolen(self):
        lock = self.path.with_name(self.path.name + ".handoff-notes.lock")
        lock.write_text('{"pid": 123}', encoding="utf-8")
        with self.assertRaises(TimeoutError):
            notes.add_note(self.path, self.note, lock_timeout=0)
        self.assertEqual(self.original, self.path.read_bytes())
        self.assertTrue(lock.exists())

    def test_intervening_edit_and_replace_failure_preserve_content(self):
        changed = self.original + b"Concurrent editor change.\n"
        real_chmod = notes.os.chmod
        def external_edit(*args):
            real_chmod(*args)
            self.path.write_bytes(changed)
        with patch.object(notes.os, "chmod", side_effect=external_edit):
            with self.assertRaises(RuntimeError):
                notes.add_note(self.path, self.note)
        self.assertEqual(changed, self.path.read_bytes())
        with patch.object(notes.os, "replace", side_effect=PermissionError("busy")):
            with self.assertRaises(PermissionError):
                notes.add_note(self.path, self.note)
        self.assertEqual(changed, self.path.read_bytes())
        self.assertEqual([self.path], list(self.path.parent.iterdir()))

    def test_fenced_example_is_not_a_section(self):
        original = self.original + b"\n```markdown\n## Handoff notes\n```\n"
        self.path.write_bytes(original)
        notes.add_note(self.path, self.note)
        self.assertTrue(self.path.read_bytes().startswith(original))
        self.assertEqual(2, self.path.read_bytes().count(b"## Handoff notes"))

    def test_invalid_input_missing_target_and_ambiguous_sections_do_not_write(self):
        for args in (("agent", "", "Request", "2026-10-14"),
                     ("user", "Source", "Request\n## Core", "2026-10-14"),
                     ("agent", "Source", "Request", "2026-02-30")):
            with self.assertRaises(ValueError):
                notes.render_note(*args)
        missing = self.path.with_name("missing.md")
        with self.assertRaises(ValueError):
            notes.add_note(missing, self.note)
        self.assertFalse(missing.exists())
        ambiguous = self.original + b"\n## Handoff notes\n\n## Another\n\n## Handoff notes\n"
        self.path.write_bytes(ambiguous)
        with self.assertRaises(ValueError):
            notes.add_note(self.path, self.note)
        self.assertEqual(ambiguous, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
