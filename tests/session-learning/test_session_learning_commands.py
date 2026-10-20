"""Public CLI contracts for bounded lookup and targeted authoring."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
import os
import re
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_session_learning_v2 import session_learning as e, v1_lesson, evidence, REPO_ROOT, SCRIPT


class CommandTests(unittest.TestCase):
    def setUp(self):
        platform = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
        fixtures = REPO_ROOT / f"temp_{platform}_live_fixture"
        fixtures.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.home = Path(self.temp.name) / "home"
        self.root.mkdir()
        self.home.mkdir()
        self.lesson = v1_lesson()
        self.lesson.update(schema_version=4, version=e.SKILL_VERSION)
        self.seed([self.lesson], [evidence()])

    def cli(self, *args, payload=None, ok=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args,
             *([] if args[0] == "hook" else ["--root", str(self.root)]), "--home-dir", str(self.home)],
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, encoding="utf-8", timeout=30, cwd=self.root,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if ok:
            self.assertEqual(0, result.returncode, result.stderr)
        else:
            self.assertNotEqual(0, result.returncode, result.stdout)
        return result

    def seed(self, lessons=(), proofs=(), authority="project"):
        changes = [{"path": f".session-learning/{folder}/{record['id']}.json", "json": record}
                   for folder, records in (("evidence", proofs), ("lessons", lessons)) for record in records]
        self.cli("apply-manifest", "-", "--authority", authority, payload={
            "manifest_schema_version": 3, "origin": "current_session", "changes": changes})

    def read(self, *args):
        return json.loads(self.cli("read", self.lesson["id"], *args).stdout)

    def proof(self, suffix="new"):
        value = evidence()
        value["id"] = f"evidence.{suffix}"
        return value

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file()}

    def test_summary_is_bounded_paged_filtered_and_legacy_search_unchanged(self):
        lessons = []
        for i in range(24):
            item = copy.deepcopy(self.lesson)
            item["id"] = f"lesson.generated.{i:02}"
            item["title"] = "Generated " + "title " * 30
            item["statement"] = "Generated " + "statement " * 40
            item["kind"] = "preference" if i % 2 else "guardrail"
            lessons.append(item)
        self.seed(lessons)
        summary = json.loads(self.cli("search", "generated", "--summary", "--json").stdout)
        self.assertEqual((25, 10, 2), (summary["total"], len(summary["items"]), summary["next_page"]))
        page2 = json.loads(self.cli("search", "generated", "--summary", "--json", "--page", "2").stdout)
        self.assertFalse({v["id"] for v in summary["items"]} & {v["id"] for v in page2["items"]})
        truncated = next(item for item in summary["items"] if item["id"] != self.lesson["id"])
        self.assertEqual(["title", "statement"], truncated["truncated_fields"])
        self.assertEqual(120, len(truncated["title"]))
        self.assertEqual(240, len(truncated["statement"]))
        self.assertNotIn("provenance", summary["items"][0])
        filtered = json.loads(self.cli("search", "generated", "--summary", "--json", "--kind", "preference",
                                       "--status", "active", "--status", "candidate", "--limit", "20").stdout)
        self.assertEqual(12, filtered["total"])
        empty = json.loads(self.cli("search", "generated", "--summary", "--json", "--page", "20").stdout)
        self.assertEqual([], empty["items"])
        self.assertIsNone(empty["next_page"])
        legacy = json.loads(self.cli("search", "generated", "--json").stdout)
        self.assertEqual(25, len(legacy))
        self.assertIn("provenance", legacy[0])
        compact = self.cli("search", "generated", "--summary", "--limit", "1").stdout
        self.assertEqual(2, len(compact.splitlines()))
        self.assertIn("next_page=2", compact)

    def test_summary_rejects_invalid_controls_and_requires_explicit_history(self):
        for flags in (("--limit", "0"), ("--limit", "21"), ("--page", "0")):
            self.cli("search", "generated", "--summary", *flags, ok=False)
        self.assertIn("require --summary", self.cli("search", "generated", "--limit", "1", ok=False).stderr)
        self.assertIn("--include-history", self.cli("search", "generated", "--summary", "--status", "retired", ok=False).stderr)
        retired = copy.deepcopy(self.lesson)
        retired.update(id="lesson.retired", status="retired", delivery=e._none_delivery())
        self.seed([retired])
        report = json.loads(self.cli("search", "generated", "--summary", "--json", "--include-history",
                                    "--status", "retired").stdout)
        self.assertEqual(["lesson.retired"], [v["id"] for v in report["items"]])

    def test_read_fields_hash_original_legacy_record_without_scanning_or_mutating(self):
        target = self.root / f".session-learning/lessons/{self.lesson['id']}.json"
        legacy = copy.deepcopy(self.lesson)
        legacy.pop("version")
        legacy["schema_version"] = 3
        target.write_text(json.dumps(legacy), encoding="utf-8")
        before = self.snapshot()
        report = self.read("--fields", "statement,scope")
        self.assertEqual({"statement", "scope"}, set(report["record"]))
        self.assertEqual(e.canonical_record_sha256(legacy), report["expected_sha256"])
        self.assertEqual(f".session-learning/lessons/{self.lesson['id']}.json", report["path"])
        with mock.patch.object(e, "_load_records", side_effect=AssertionError("whole-store scan")), \
                mock.patch.object(e, "recover_transactions", side_effect=AssertionError("recovery")):
            full = e.read_record(self.root, self.lesson["id"])
        self.assertEqual(legacy, full["record"])
        self.assertEqual(before, self.snapshot())

    def test_read_evidence_invalid_fields_missing_ids_and_path_escape(self):
        report = json.loads(self.cli("read", evidence()["id"], "--type", "evidence").stdout)
        self.assertEqual(evidence(), report["record"])
        for fields in ("", "unknown", "statement,missing", "statement,"):
            self.cli("read", self.lesson["id"], "--fields", fields, ok=False)
        for identity in ("../escape", "lesson.missing", "C:/outside"):
            self.cli("read", identity, ok=False)
        self.cli("read", evidence()["id"], ok=False)

    def test_read_legacy_evidence_preserves_original_fields_and_hash(self):
        proof = evidence()
        proof["schema_version"] = 1
        proof.pop("authority")
        target = self.root / f".session-learning/evidence/{proof['id']}.json"
        target.write_text(json.dumps(proof), encoding="utf-8")
        report = json.loads(self.cli("read", proof["id"], "--type", "evidence").stdout)
        self.assertEqual(proof, report["record"])
        self.assertEqual(e.canonical_record_sha256(proof), report["expected_sha256"])

    def test_read_refuses_interrupted_transaction_without_recovery(self):
        journal = self.root / ".session-learning/.transactions/interrupted/journal.json"
        journal.parent.mkdir(parents=True)
        journal.write_text("{}", encoding="utf-8")
        before = self.snapshot()
        self.assertIn("interrupted transaction", self.cli("read", self.lesson["id"], ok=False).stderr)
        self.assertEqual(before, self.snapshot())

    def test_single_authority_reads_and_submissions_do_not_cross_stores(self):
        local = copy.deepcopy(self.lesson)
        local["authority"] = "local"
        local["delivery"]["instruction_path"] = None
        proof = evidence()
        proof["authority"] = "local"
        self.seed([local], [proof], authority="local")
        report = self.read("--authority", "local")
        self.assertEqual("local", report["record"]["authority"])
        local_proof = self.proof("local")
        local_proof["authority"] = "local"
        self.cli("submit-evidence", "--lesson", local["id"], "--evidence", "-", "--authority", "local", payload=local_proof)
        before = self.snapshot()
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence-id", local_proof["id"], ok=False)
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence", "-", payload=local_proof, ok=False)
        self.assertEqual(before, self.snapshot())

    def test_submit_creates_and_links_once_without_changing_guidance_or_usage(self):
        before = self.read()["record"]
        proof = self.proof()
        first = json.loads(self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence", "-", payload=proof).stdout)
        self.assertTrue(first["changed"])
        after = self.read()["record"]
        self.assertEqual(before["provenance"] + [{"evidence_id": proof["id"], "signal": proof["signal"]}], after["provenance"])
        for field in set(before) - {"provenance", "timestamps"}:
            self.assertEqual(before[field], after[field], field)
        snapshot = self.snapshot()
        for flags, payload in ((("--evidence", "-"), proof), (("--evidence-id", proof["id"]), None)):
            result = json.loads(self.cli("submit-evidence", "--lesson", self.lesson["id"], *flags, payload=payload).stdout)
            self.assertFalse(result["changed"])
            self.assertEqual(snapshot, self.snapshot())

    def test_submit_reuses_existing_evidence_and_rejects_conflicting_or_invalid_records(self):
        proof = self.proof()
        self.seed(proofs=[proof])
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence-id", proof["id"])
        before = self.snapshot()
        conflicting = {**proof, "feedback": "Different interpretation."}
        self.assertIn("different content", self.cli("submit-evidence", "--lesson", self.lesson["id"],
                                                    "--evidence", "-", payload=conflicting, ok=False).stderr)
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence", "-", payload={"id": "evidence.invalid"}, ok=False)
        self.cli("submit-evidence", "--lesson", "lesson.missing", "--evidence", "-", payload=self.proof("orphan"), ok=False)
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence-id", "evidence.missing", ok=False)
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence", "-", payload=[proof], ok=False)
        self.assertEqual(before, self.snapshot())

    def test_write_failure_rolls_back_new_evidence_and_lesson(self):
        before = self.snapshot()
        original = e._atomic_write_bytes
        failed = False

        def fail_lesson_once(target, value):
            nonlocal failed
            if Path(target).name == f"{self.lesson['id']}.json" and not failed:
                failed = True
                raise PermissionError("blocked lesson write")
            return original(target, value)

        with mock.patch.object(e, "_atomic_write_bytes", side_effect=fail_lesson_once):
            with self.assertRaises(PermissionError):
                e.submit_evidence(self.root, self.lesson["id"], evidence=self.proof(), home_dir=self.home)
        self.assertTrue(failed)
        self.assertEqual(before, self.snapshot())

    def test_concurrent_confirmations_preserve_both_appends(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.cli, "submit-evidence", "--lesson", self.lesson["id"],
                                   "--evidence", "-", payload=self.proof(suffix)) for suffix in ("one", "two")]
            for future in futures:
                future.result()
        references = {item["evidence_id"] for item in self.read()["record"]["provenance"]}
        self.assertTrue({"evidence.one", "evidence.two"} <= references)
        self.cli("audit", "--authority", "both")

    def test_update_requires_hash_except_pure_confirmation(self):
        proof = self.proof()
        self.seed(proofs=[proof])
        confirm = {"intent": "confirm", "operations": [{"op": "append_provenance", "value": {
            "evidence_id": proof["id"], "signal": proof["signal"]}}]}
        self.cli("update-lesson", self.lesson["id"], "-", payload=confirm)
        before = self.snapshot()
        for extra in ({"usage_update": {}}, {"equivalence_update": {"value": None, "rationale": "review"}}):
            self.cli("update-lesson", self.lesson["id"], "-", payload={**confirm, **extra}, ok=False)
        exception = {"intent": "add_exception", "operations": [{"op": "append_exception", "value": "Archived clients are exempt."}]}
        self.assertIn("expected_sha256", self.cli("update-lesson", self.lesson["id"], "-", payload=exception, ok=False).stderr)
        self.assertEqual(before, self.snapshot())
        exception["expected_sha256"] = self.read("--fields", "statement,exceptions")["expected_sha256"]
        self.cli("update-lesson", self.lesson["id"], "-", payload=exception)
        snapshot = self.snapshot()
        self.assertIn("stale lesson patch", self.cli("update-lesson", self.lesson["id"], "-", payload=exception, ok=False).stderr)
        self.assertEqual(snapshot, self.snapshot())

    def test_update_preserves_intent_and_maintenance_guards(self):
        report = self.read("--fields", "scope,triggers")
        patch = {"expected_sha256": report["expected_sha256"], "intent": "extend", "operations": [
            {"op": "append_triggers", "value": ["additional trigger"]}]}
        self.assertIn("requires operations: replace_scope", self.cli("update-lesson", self.lesson["id"], "-", payload=patch, ok=False).stderr)
        patch = {"expected_sha256": report["expected_sha256"], "intent": "add_exception", "operations": [
            {"op": "append_exception", "value": "Archived clients are exempt."}]}
        self.assertIn("expected_store_revision", self.cli("update-lesson", self.lesson["id"], "-", "--origin", "maintenance", payload=patch, ok=False).stderr)
        context = json.loads(self.cli("reflection-context", "--authority", "project").stdout)
        self.cli("update-lesson", self.lesson["id"], "-", "--origin", "maintenance", "--expected-store-revision",
                 context["revisions"]["project"], payload=patch)
        self.cli("update-lesson", self.lesson["id"], "-", "--origin", "maintenance", "--expected-store-revision",
                 context["revisions"]["project"], payload=patch, ok=False)

    def test_read_and_submission_confine_symlink_targets(self):
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text(json.dumps(self.proof("escaped")), encoding="utf-8")
        link = self.root / ".session-learning/evidence/evidence.escaped.json"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.cli("read", "evidence.escaped", "--type", "evidence", ok=False)
        self.cli("submit-evidence", "--lesson", self.lesson["id"], "--evidence-id", "evidence.escaped", ok=False)
        self.assertEqual(self.proof("escaped"), json.loads(outside.read_text(encoding="utf-8")))

    def test_documented_workflow_uses_public_commands_for_lookup_confirmation_and_related_lesson(self):
        reference = (SCRIPT.parent.parent / "references/patch-authoring.md").read_text(encoding="utf-8")
        records = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", reference, re.S)]
        proof = next(record for record in records if record.get("record_type") == "evidence")
        typed_patch = next(record for record in records if record.get("intent") == "add_exception")
        manifest = next(record for record in records if "manifest_schema_version" in record)
        commands = re.findall(r"```text\n(.*?)\n```", reference, re.S)

        def run_recipe(block):
            outputs = []
            for line in block.splitlines():
                args = shlex.split(line.replace(" --root <root>", ""))[2:]
                result = self.cli(*args)
                outputs.append(json.loads(result.stdout) if args[0] not in {"audit"} else result.stdout)
            return outputs

        general = copy.deepcopy(self.lesson)
        general.update(id="lesson.experiment-providers", title="Separate experiment providers",
                       statement="Console experiments use separate provider modules and prefixes.",
                       triggers=["experiment providers"], safe_path=["Use a separate provider module and prefix."])
        loose = []
        for i in range(23):
            item = copy.deepcopy(self.lesson)
            item.update(id=f"lesson.loose.{i:02}", safe_path=["Inspect experiment diagnostics."])
            loose.append(item)
        self.seed([general, *loose])
        lookup = next(block for block in commands if " search " in block)
        summary, selected = run_recipe(lookup)
        self.assertGreater(summary["total"], summary["limit"])
        self.assertEqual(general["id"], summary["items"][0]["id"])
        self.assertNotIn("provenance", selected["record"])

        # Confirmation needs neither a full lesson read nor a caller-computed hash.
        (self.root / "evidence.json").write_text(json.dumps(proof), encoding="utf-8")
        submit, audit = run_recipe(next(block for block in commands if " submit-evidence " in block))
        self.assertTrue(submit["changed"])
        after = json.loads(self.cli("read", general["id"]).stdout)["record"]
        for field in set(general) - {"provenance", "timestamps"}:
            self.assertEqual(general[field], after[field], field)
        self.assertEqual(general["provenance"] + [{"evidence_id": proof["id"], "signal": proof["signal"]}], after["provenance"])

        # The documented single-field append uses the hash returned by selective read.
        selected = run_recipe(lookup)[1]
        typed_patch["expected_sha256"] = selected["expected_sha256"]
        (self.root / "patch.json").write_text(json.dumps(typed_patch), encoding="utf-8")
        run_recipe(next(block for block in commands if " update-lesson " in block))

        # Extend the documented advanced manifest with one complete new related lesson.
        advanced = next(block for block in commands if " apply-manifest " in block)
        read_line, *apply_lines = advanced.splitlines()
        selected = run_recipe(read_line)[0]
        manifest["changes"][0]["lesson_patch"]["expected_sha256"] = selected["expected_sha256"]
        narrower = copy.deepcopy(general)
        narrower.update(id="lesson.perk-provider", title="Perk experiment provider",
                        statement="Perk experiments use a separate provider and the perk prefix.",
                        triggers=["perk experiments"], safe_path=["Use the perk provider and prefix."],
                        provenance=[{"evidence_id": proof["id"], "signal": proof["signal"]}],
                        relationships={"supersedes": [], "related": [general["id"]]})
        manifest["changes"].append({"path": f".session-learning/lessons/{narrower['id']}.json", "json": narrower})
        (self.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        run_recipe("\n".join(apply_lines))
        self.assertEqual(narrower, json.loads(self.cli("read", narrower["id"]).stdout)["record"])

        # A recorded hook diagnostic remains visible after repairing its current cause.
        retrieval = self.root / ".session-learning/retrieval.json"
        retrieval.write_text("{invalid", encoding="utf-8")
        self.cli("hook", "--host", "codex", "--data-dir", str(Path(self.temp.name) / "host-data"), payload={
            "hook_event_name": "UserPromptSubmit", "cwd": str(self.root), "session_id": "example-session",
            "prompt": "Inspect experiment providers."})
        self.cli("rebuild-index")
        audit = json.loads(self.cli("audit", "--authority", "both", "--json").stdout)
        self.assertTrue(audit["hook_errors"])
        self.assertEqual([], audit["validation_errors"])


if __name__ == "__main__":
    unittest.main()
