"""Observable contracts for conditional capture, acceptance, activity, reflection."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_session_learning_v2 import session_learning as e, v1_lesson, evidence, REPO_ROOT

x = e._extensions()


def draft(event="event-one", statement=None):
    return {"target_authority": "project", "source": {"host": "codex", "session_id": "session-one", "event_ids": [event]},
        "signal": "explicit_user_correction", "observation": {
            "situation": "Generated API response changed.", "attempted_behavior": "Edited generated output.",
            "feedback": "Schema is authoritative.", "corrected_behavior": "Regenerated from schema.",
            "outcome": "Targeted contract checks passed."},
        "proposed_guidance": {"statement": statement or "Update the schema before regenerating this client.",
            "scope": {"type": "paths", "paths": ["schemas/**"]}, "triggers": ["generated client"],
            "safe_path": ["update schema", "regenerate", "verify contract"], "exceptions": []}, "verification_gaps": []}


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        platform = "windows" if sys.platform == "win32" else "macos" if sys.platform == "darwin" else "linux"
        fixtures = REPO_ROOT / f"temp_{platform}_live_fixture"
        fixtures.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.data = Path(self.temp.name) / "host-data"
        self.data.mkdir()

    def enabled(self):
        return x.configure(e, self.root, home=self.home, drafting=True)

    def hook(self, event="UserPromptSubmit", **extra):
        (self.root / ".session-learning").mkdir(exist_ok=True)
        payload = {"hook_event_name": event, "cwd": str(self.root), "session_id": "session-one", **extra}
        return e.handle_hook_event(payload, host="codex", data_dir=self.data, home_dir=self.home)

    def seed(self, authority="project"):
        lesson, proof = v1_lesson(), evidence()
        lesson.update(schema_version=4, version=e.SKILL_VERSION, authority=authority)
        proof["authority"] = authority
        if authority == "local":
            lesson["delivery"]["instruction_path"] = None
        manifest = {"manifest_schema_version": 2, "origin": "current_session", "changes": [
            {"path": f".session-learning/evidence/{proof['id']}.json", "json": proof},
            {"path": f".session-learning/lessons/{lesson['id']}.json", "json": lesson}]}
        e.apply_manifest(self.root, manifest, authority=authority, home_dir=self.home)
        return manifest, lesson

    def test_absent_configuration_is_read_only_and_disabled(self):
        report = x.configure(e, self.root, home=self.home)
        self.assertFalse(report["effective"]["drafting_enabled"])
        self.assertTrue(report["effective"]["activity_audit_enabled"])
        self.assertEqual([], list(self.root.iterdir()))
        self.assertEqual([], list(self.home.iterdir()))

    def test_hook_activity_without_learning_store_or_configuration(self):
        (self.root / ".git").mkdir()
        nested = self.root / "src"
        nested.mkdir()
        for event in ("SessionStart", "UserPromptSubmit", "SessionEnd"):
            result = e.handle_hook_event({"hook_event_name": event, "source": "startup", "cwd": str(nested),
                "session_id": "empty-project", "prompt": "Ordinary work."}, host="codex", data_dir=self.data, home_dir=self.home)
            self.assertEqual({}, result)
        self.assertFalse((self.root / ".session-learning").exists())
        self.assertEqual([], list(self.home.iterdir()))
        self.assertEqual(3, x.activity(e, self.root, home=self.home, data_dir=self.data)["counts"]["hook_events"])
        x.configure(e, self.root, home=self.home, scope="user", audit=False)
        before = {p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()}
        e.handle_hook_event({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(nested),
            "session_id": "no-audit"}, host="codex", data_dir=self.data, home_dir=self.home)
        self.assertEqual(before, {p: p.read_bytes() for p in self.data.rglob("*") if p.is_file()})

    def test_nested_repository_cannot_inherit_parent_drafting_consent(self):
        self.enabled()
        child = self.root / "child"
        child.mkdir()
        (child / ".git").mkdir()
        self.assertIsNone(e.find_learning_root(child, home_dir=self.home))
        result = e.handle_hook_event({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(child),
            "session_id": "child-session"}, host="codex", data_dir=self.data, home_dir=self.home)
        self.assertEqual({}, result)
        self.assertFalse((child / ".session-learning").exists())

    def test_configuration_precedence_and_no_shared_consent(self):
        personal = self.home / ".agents/session-learning/config.json"
        personal.parent.mkdir(parents=True)
        personal.write_text(json.dumps({"schema_version": 1, "drafting_enabled": True, "max_lessons_per_event": 1}))
        shared = self.root / ".session-learning/config.json"
        shared.parent.mkdir()
        shared.write_text(json.dumps({"schema_version": 1, "drafting_enabled": True, "max_lessons_per_event": 2}))
        report = x.configure(e, self.root, home=self.home)
        self.assertFalse(report["effective"]["drafting_enabled"])
        self.assertEqual(2, report["effective"]["max_lessons_per_event"])
        report = self.enabled()
        private = Path(report["changed_file"])
        value = json.loads(private.read_text())
        value["max_lessons_per_event"] = 4
        private.write_text(json.dumps(value))
        self.assertEqual(4, e._load_config(self.root, self.home)["max_lessons_per_event"])
        other_home = Path(self.temp.name) / "other-home"
        self.assertFalse(e._load_config(self.root, other_home)["drafting_enabled"])
        self.assertEqual(str(private), report["sources"]["drafting_enabled"])

    def test_user_scope_cannot_enable_drafting_and_preserves_unrelated_values(self):
        with self.assertRaises(ValueError):
            x.configure(e, self.root, home=self.home, scope="user", drafting=True)
        report = x.configure(e, self.root, home=self.home, scope="user", audit=False)
        path = Path(report["changed_file"])
        value = json.loads(path.read_text())
        value["python_path"] = "kept-unrelated"
        path.write_text(json.dumps(value))
        x.configure(e, self.root, home=self.home, scope="user", audit=True)
        self.assertEqual("kept-unrelated", json.loads(path.read_text())["python_path"])

    def test_invalid_private_configuration_fails_closed(self):
        report = self.enabled()
        Path(report["changed_file"]).write_text("not JSON")
        inspected = x.configuration(e, self.root, self.home)
        self.assertFalse(inspected["effective"]["drafting_enabled"])
        self.assertTrue(inspected["issues"])

    def test_project_configuration_is_excluded_without_tracked_changes(self):
        result = x.git(self.root, "init")
        self.assertEqual(0, result.returncode, result.stderr)
        self.enabled()
        status = x.git(self.root, "status", "--porcelain").stdout
        self.assertEqual("", status)
        self.assertIn("config.local.json", (self.root / ".git/info/exclude").read_text())
        x.git(self.root, "add", "-f", ".session-learning/config.local.json")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.enabled()

    def test_disabled_hooks_and_helpers_emit_no_drafting_context(self):
        self.assertEqual({}, self.hook("SessionStart", source="startup"))
        for _ in range(15):
            self.assertEqual({}, self.hook(prompt="ordinary work"))
        self.assertEqual({"enabled": False}, x.draft_context(e, self.root, home=self.home))
        self.assertEqual("disabled", x.save_draft(e, self.root, draft(), home=self.home)["reason"])
        self.assertFalse((x.staging(e, self.root, self.home) / "drafts").exists())

    def test_queued_capture_rechecks_consent_inside_writer_lock(self):
        self.enabled()
        original_lock = e.writer_lock
        from contextlib import contextmanager
        @contextmanager
        def turn_off_before_acquiring(root, *, authority):
            # Simulate configure winning the writer race after the initial read.
            private = self.root / ".session-learning/config.local.json"
            config = json.loads(private.read_text())
            config["drafting_enabled"] = False
            private.write_text(json.dumps(config))
            with original_lock(root, authority=authority):
                yield
        with mock.patch.object(e, "writer_lock", turn_off_before_acquiring):
            result = x.save_draft(e, self.root, draft(), home=self.home)
        self.assertEqual({"saved": False, "reason": "disabled"}, result)
        self.assertEqual([], x.drafts(e, self.root, self.home)[0])

    def test_boundary_only_exposure_toggle_and_retrieval_independence(self):
        self.enabled()
        initial = self.hook("SessionStart", source="startup")
        self.assertIn("draft-context", initial["hookSpecificOutput"]["additionalContext"])
        for _ in range(15):
            self.assertEqual({}, self.hook(prompt="normal task"))
        restored = self.hook("SessionStart", source="compact")
        self.assertIn("draft-context", restored["hookSpecificOutput"]["additionalContext"])
        self.assertEqual({}, self.hook("PreToolUse", tool_input={"path": "schemas/api.json"}))
        x.configure(e, self.root, home=self.home, drafting=False)
        self.assertIn("disabled", self.hook()["hookSpecificOutput"]["additionalContext"])
        self.assertEqual({}, self.hook())
        self.enabled()
        shared = self.root / ".session-learning/config.json"
        shared.write_text(json.dumps({"schema_version": 1, "retrieval_enabled": False}))
        self.assertIn("draft-context", self.hook()["hookSpecificOutput"]["additionalContext"])

    def test_first_prompt_fallback_and_budget_does_not_consume_pending_pointer(self):
        report = self.enabled()
        path = Path(report["changed_file"])
        value = json.loads(path.read_text())
        value["max_context_characters"] = 1
        path.write_text(json.dumps(value))
        self.assertEqual({}, self.hook())
        value["max_context_characters"] = 4000
        path.write_text(json.dumps(value))
        self.assertIn("draft-context", self.hook()["hookSpecificOutput"]["additionalContext"])

    def test_capture_deduplication_revision_and_terminal_reopening(self):
        self.enabled()
        saved = x.save_draft(e, self.root, draft(), home=self.home, data_dir=self.data)
        duplicate = x.save_draft(e, self.root, draft("other-event"), home=self.home, data_dir=self.data)
        self.assertEqual("duplicate", duplicate["reason"])
        x.review_draft(e, self.root, saved["id"], saved["expected_sha256"], "dismissed", "low_impact", home=self.home)
        terminal = x.drafts(e, self.root, self.home)[0][0]
        self.assertEqual(0, x.pending(e, self.root, home=self.home)["total"])
        changed = draft(statement="Update the schema and verify the public API contract.")
        with self.assertRaisesRegex(ValueError, "stale"):
            x.save_draft(e, self.root, changed, home=self.home, draft_id=saved["id"], expected_sha256=saved["expected_sha256"])
        reopened = x.save_draft(e, self.root, changed, home=self.home, draft_id=saved["id"], expected_sha256=e.canonical_record_sha256(terminal))
        self.assertTrue(reopened["saved"])
        self.assertEqual(1, x.pending(e, self.root, home=self.home)["total"])

    def test_drafts_never_enter_canonical_indexes_and_unverified_is_preserved(self):
        self.enabled()
        value = draft()
        value["observation"]["outcome"] = "Not yet verified."
        value["verification_gaps"] = ["Run the contract check after regeneration."]
        x.save_draft(e, self.root, value, home=self.home)
        self.assertFalse((self.root / ".session-learning/lessons").exists())
        self.assertFalse((self.root / ".session-learning/index.md").exists())
        self.assertEqual(value["verification_gaps"], x.pending(e, self.root, home=self.home)["items"][0]["verification_gaps"])

    def test_privacy_scope_and_size_rejection(self):
        self.enabled()
        for text in ("API_KEY=secret", "name@example.com", "C:/other/private/file", "a" * 501):
            value = draft()
            value["observation"]["feedback"] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                x.save_draft(e, self.root, value, home=self.home)
        value = draft()
        value["proposed_guidance"]["scope"]["paths"] = ["../escape"]
        with self.assertRaises(ValueError):
            x.save_draft(e, self.root, value, home=self.home)

    def test_backlog_warning_pagination_age_and_reset(self):
        self.enabled()
        outcomes = [x.save_draft(e, self.root, draft(f"event-{i}", f"Verify schema contract case {i}."), home=self.home) for i in range(51)]
        self.assertIsNone(outcomes[48]["warning"])
        self.assertTrue(outcomes[49]["warning"])
        self.assertIsNone(outcomes[50]["warning"])
        view = x.pending(e, self.root, home=self.home)
        self.assertEqual(51, view["total"])
        self.assertEqual(20, len(view["items"]))
        self.assertIn("age_days", view["items"][0])
        for item in view["items"][:2]:
            x.review_draft(e, self.root, item["id"], item["expected_sha256"], "dismissed", "low_impact", home=self.home)
        saved = x.save_draft(e, self.root, draft("new-event", "Verify a newly discovered response invariant."), home=self.home)
        self.assertTrue(saved["warning"])

    def test_acceptance_creates_active_pointer_in_fresh_project(self):
        self.enabled()
        saved = x.save_draft(e, self.root, draft(), home=self.home)
        lesson, proof = v1_lesson(), evidence()
        lesson.update(schema_version=4, version=e.SKILL_VERSION, authority="project")
        manifest = {"manifest_schema_version": 2, "origin": "current_session", "changes": [
            {"path": f".session-learning/evidence/{proof['id']}.json", "json": proof},
            {"path": f".session-learning/lessons/{lesson['id']}.json", "json": lesson}]}
        self.assertFalse((self.root / "AGENTS.md").exists())
        x.accept_draft(e, self.root, saved["id"], saved["expected_sha256"], manifest, home=self.home)
        self.assertIn("session-learning:index", (self.root / "AGENTS.md").read_text())
        self.assertEqual("accepted", x.drafts(e, self.root, self.home)[0][0]["disposition"])
        self.assertEqual([], e.audit_store(self.root, authority="both", home_dir=self.home)["validation_errors"])
        # Deferring surfaces during preparation never weakens final validation.
        (self.root / "AGENTS.md").write_text("Pointer removed externally.\n")
        self.assertTrue(e.audit_store(self.root, home_dir=self.home)["validation_errors"])

    def test_acceptance_recovers_after_commit_before_disposition(self):
        self.enabled()
        manifest, _ = self.seed()
        # Start from an empty canonical store while retaining staging enrollment.
        for directory in ("lessons", "evidence"):
            for path in (self.root / ".session-learning" / directory).glob("*.json"):
                path.unlink()
        for name in ("index.md", "retrieval.json"):
            (self.root / ".session-learning" / name).unlink()
        saved = x.save_draft(e, self.root, draft(), home=self.home)
        with mock.patch.object(x, "review_draft", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                x.accept_draft(e, self.root, saved["id"], saved["expected_sha256"], manifest, home=self.home)
        self.assertEqual("pending", x.pending(e, self.root, home=self.home)["items"][0]["disposition"])
        recovered = x.recover_acceptance(e, self.root, home=self.home)
        self.assertEqual("accepted", recovered["operations"][0]["disposition"])
        self.assertEqual([], e.validate_store(self.root, home_dir=self.home))
        self.assertEqual([], x.recover_acceptance(e, self.root, home=self.home)["operations"])

    def test_receipt_replay_and_operation_identity(self):
        manifest, _ = self.seed()
        manifest["manifest_schema_version"] = 3
        manifest["operation_id"] = "operation.one"
        # Existing record updates need patches; use a new proof-only operation.
        proof = evidence()
        proof["id"] = "evidence.second"
        manifest["changes"] = [{"path": ".session-learning/evidence/evidence.second.json", "json": proof}]
        result = e.apply_manifest(self.root, manifest, home_dir=self.home)
        self.assertTrue(result["changed"])
        replay = e.apply_manifest(self.root, manifest, home_dir=self.home)
        self.assertTrue(replay["replayed"])
        manifest["changes"][0]["json"]["feedback"] = "Changed meaning."
        with self.assertRaisesRegex(ValueError, "different changes"):
            e.apply_manifest(self.root, manifest, home_dir=self.home)

    def test_activity_matches_actual_emissions_and_live_sessions(self):
        self.seed()
        self.enabled()
        self.hook("SessionStart", source="startup")
        result = self.hook(prompt="generated clients")
        self.assertTrue(result)
        context = x.draft_context(e, self.root, home=self.home, data_dir=self.data)
        self.assertTrue(context["enabled"])
        before = x.activity(e, self.root, home=self.home, data_dir=self.data)
        self.assertEqual(1, before["counts"]["drafting_pointer_emissions"])
        self.assertEqual(1, before["counts"]["lesson_emissions"])
        self.assertEqual(1, before["counts"]["drafting_instruction_emissions"])
        self.assertEqual(1, before["live_sessions"])
        self.hook("SessionEnd")
        after = x.activity(e, self.root, home=self.home, data_dir=self.data)
        before["counts"]["hook_events"] += 1
        self.assertEqual(before["counts"], after["counts"])
        self.assertEqual(0, after["live_sessions"])
        self.assertNotIn("generated clients", json.dumps(after))
        self.assertNotIn(str(self.root), json.dumps(after))

    def test_audit_disable_and_failures_do_not_change_capture_or_retrieval(self):
        self.enabled()
        x.configure(e, self.root, home=self.home, audit=False)
        result = self.hook("SessionStart", source="startup")
        self.assertIn("draft-context", result["hookSpecificOutput"]["additionalContext"])
        self.assertTrue(x.save_draft(e, self.root, draft(), home=self.home, data_dir=self.data)["saved"])
        self.assertFalse(x.activity(e, self.root, home=self.home, data_dir=self.data)["counts"])
        x.configure(e, self.root, home=self.home, audit=True)
        with mock.patch.object(e, "_atomic_write_bytes", side_effect=PermissionError):
            x.add_activity(e, self.root, {"hook_events": 1}, home=self.home, data_dir=self.data)

    def test_aggregate_retention_and_concurrent_updates(self):
        expired = (datetime.now(timezone.utc).date() - timedelta(days=91)).isoformat()
        old = x.activity_file(e, self.root, self.data, expired)
        old.write_text(json.dumps({"schema_version": 1, "counts": {"hook_events": 100}, "lessons": {}}))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: x.add_activity(e, self.root, {"hook_events": 1}, home=self.home, data_dir=self.data), range(12)))
        report = x.activity(e, self.root, home=self.home, data_dir=self.data)
        self.assertFalse(old.exists())
        self.assertEqual(12, report["counts"]["hook_events"])

    def maintenance(self, changes, revision=None):
        return {"manifest_schema_version": 3, "origin": "maintenance", "changes": changes,
                "expected_store_revision": revision or x.store_revision(e, self.root, "project", self.home)}

    def test_reflection_pagination_guards_evidence_cases_and_instruction_surfaces(self):
        self.seed()
        extra = []
        for i in range(21):
            lesson = v1_lesson()
            lesson["id"] = f"lesson.additional.{i:03}"
            extra.append({"path": f".session-learning/lessons/{lesson['id']}.json", "json": lesson})
        e.apply_manifest(self.root, {"manifest_schema_version": 2, "origin": "current_session", "changes": extra}, home_dir=self.home)
        page = x.reflection_context(e, self.root, home=self.home)
        self.assertEqual(20, len(page["items"]))
        self.assertEqual(22, page["total"])
        self.assertTrue(page["health"]["can_author"])
        self.assertEqual(2, len(x.reflection_context(e, self.root, home=self.home, page=2, expected=page["revisions"])["items"]))
        with self.assertRaisesRegex(ValueError, "original revisions"):
            x.reflection_context(e, self.root, home=self.home, page=2)
        for path in (self.root / "AGENTS.md", self.root / ".session-learning/evidence/evidence.20260827.generated-files.001.json",
                     self.root / ".session-learning/cases/case.extra.json"):
            before = x.store_revision(e, self.root, "project", self.home)
            content = path.read_bytes() if path.exists() else None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"external change")
            self.assertNotEqual(before, x.store_revision(e, self.root, "project", self.home))
            with self.assertRaisesRegex(ValueError, "invalidated"):
                x.reflection_context(e, self.root, home=self.home, page=2, expected=page["revisions"])
            path.write_bytes(content) if content is not None else path.unlink()

    def test_reflection_summaries_bound_long_fields_and_match_scope_topics(self):
        manifest, lesson = self.seed()
        raw = copy.deepcopy(lesson)
        raw["id"] = "lesson.bounded"
        raw["statement"] = "Specific useful guidance. " * 100
        raw["triggers"] = [f"trigger {i}" for i in range(30)]
        raw["scope"]["paths"] = ["distinct-component/**"]
        e.apply_manifest(self.root, {"manifest_schema_version": 2, "origin": "current_session", "changes": [
            {"path": ".session-learning/lessons/lesson.bounded.json", "json": raw}]}, home_dir=self.home)
        result = x.reflection_context(e, self.root, home=self.home, query="distinct-component")
        item = result["items"][0]
        self.assertEqual(1, result["total"])
        self.assertEqual(500, len(item["statement"]))
        self.assertEqual(20, len(item["triggers"]))
        self.assertEqual(["statement", "triggers"], item["truncated_fields"])
        self.assertEqual(e.canonical_record_sha256(json.loads((self.root / ".session-learning/lessons/lesson.bounded.json").read_text())), item["expected_sha256"])

    def test_reflection_reads_both_authorities_and_has_no_draft_or_activity_side_effect(self):
        self.seed()
        self.seed(authority="local")
        self.enabled()
        x.save_draft(e, self.root, draft(), home=self.home)
        before = x.activity(e, self.root, home=self.home)
        context = x.reflection_context(e, self.root, home=self.home)
        self.assertEqual({"project", "local"}, {item["authority"] for item in context["items"]})
        self.assertEqual(2, context["total"])
        self.assertEqual(before, x.activity(e, self.root, home=self.home))
        self.assertEqual(1, x.pending(e, self.root, home=self.home)["total"])

    def test_guarded_noop_changes_no_canonical_bytes_and_records_review(self):
        self.seed()
        directory = self.root / ".session-learning"
        original = {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()}
        for _ in range(2):
            self.assertFalse(e.apply_manifest(self.root, self.maintenance([]), home_dir=self.home)["changed"])
        self.assertEqual(original, {p: p.read_bytes() for p in directory.rglob("*") if p.is_file()})
        self.assertEqual(2, x.activity(e, self.root, home=self.home)["counts"]["maintenance_noop"])
        stale = self.maintenance([])
        (self.root / "AGENTS.md").write_text("New enforcement instructions.")
        with self.assertRaisesRegex(ValueError, "stale authority"):
            e.apply_manifest(self.root, stale, home_dir=self.home)

    def test_reflection_rejects_fresh_evidence_and_manufactured_usage(self):
        self.seed()
        proof = evidence()
        proof["id"] = "evidence.new"
        with self.assertRaisesRegex(ValueError, "existing evidence"):
            e.apply_manifest(self.root, self.maintenance([{"path": ".session-learning/evidence/evidence.new.json", "json": proof}]), home_dir=self.home)
        lesson = v1_lesson()
        lesson["id"] = "lesson.synthetic"
        lesson["usage"]["confirmations"] = 2
        with self.assertRaisesRegex(ValueError, "historical usage"):
            e.apply_manifest(self.root, self.maintenance([{"path": ".session-learning/lessons/lesson.synthetic.json", "json": lesson}]), home_dir=self.home)

    def test_transactional_consolidation_preserves_sources_and_exception_gate(self):
        _, source = self.seed()
        source_path = self.root / ".session-learning/lessons" / (source["id"] + ".json")
        old = json.loads(source_path.read_text())
        old["exceptions"] = ["Hand-authored fixtures are edited directly."]
        source_path.write_text(json.dumps(old))
        e.rebuild_index(self.root)
        replacement = copy.deepcopy(old)
        replacement["id"] = "lesson.consolidated"
        replacement["relationships"]["supersedes"] = [old["id"]]
        patch = {"expected_sha256": e.canonical_record_sha256(old), "intent": "supersede", "operations": [
            {"op": "set_status", "value": "superseded"}, {"op": "set_delivery_none"}]}
        changes = [{"path": ".session-learning/lessons/lesson.consolidated.json", "json": replacement},
                   {"path": f".session-learning/lessons/{old['id']}.json", "lesson_patch": patch}]
        replacement["exceptions"] = []
        with self.assertRaisesRegex(ValueError, "source exceptions"):
            e.apply_manifest(self.root, self.maintenance(changes), home_dir=self.home)
        self.assertEqual(old, json.loads(source_path.read_text()))
        replacement["exceptions"] = old["exceptions"]
        replacement["provenance"] = []
        with self.assertRaisesRegex(ValueError, "source provenance"):
            e.apply_manifest(self.root, self.maintenance(changes), home_dir=self.home)
        replacement["provenance"] = old["provenance"]
        result = e.apply_manifest(self.root, self.maintenance(changes), home_dir=self.home)
        self.assertTrue(result["changed"])
        stored = json.loads(source_path.read_text())
        self.assertEqual("superseded", stored["status"])
        self.assertEqual(old["usage"], stored["usage"])
        self.assertEqual([], e.validate_store(self.root, home_dir=self.home))

    def test_prepared_acceptance_freezes_revision_until_explicit_cancel(self):
        self.enabled()
        manifest, _ = self.seed()
        saved = x.save_draft(e, self.root, draft(), home=self.home)
        with mock.patch.object(e, "apply_manifest", side_effect=PermissionError("write blocked")):
            with self.assertRaises(PermissionError):
                x.accept_draft(e, self.root, saved["id"], saved["expected_sha256"], manifest, home=self.home)
        with self.assertRaisesRegex(ValueError, "prepared acceptance"):
            x.review_draft(e, self.root, saved["id"], saved["expected_sha256"], "dismissed", "unsupported", home=self.home)
        operations = list((x.staging(e, self.root, self.home) / "acceptance").glob("*.json"))
        self.assertTrue(x.cancel_acceptance(e, self.root, operations[0].stem, home=self.home)["canceled"])
        self.assertEqual("dismissed", x.review_draft(e, self.root, saved["id"], saved["expected_sha256"], "dismissed", "unsupported", home=self.home)["disposition"])

    def test_capture_permission_failure_does_not_fallback_to_repository(self):
        self.enabled()
        with mock.patch.object(e, "_atomic_write_bytes", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                x.save_draft(e, self.root, draft(), home=self.home)
        self.assertFalse((self.root / ".session-learning/drafts").exists())

    def test_survivor_consolidation_uses_bounded_typed_append_batches(self):
        _, survivor = self.seed()
        proof = evidence()
        proof["id"] = "evidence.source"
        source = v1_lesson()
        source["id"] = "lesson.source"
        source["provenance"] = [{"evidence_id": proof["id"], "signal": proof["signal"]}]
        source["exceptions"] = ["A curated fixture has no generator.", "Schema migration has a manual phase."]
        e.apply_manifest(self.root, {"manifest_schema_version": 2, "origin": "current_session", "changes": [
            {"path": ".session-learning/evidence/evidence.source.json", "json": proof},
            {"path": ".session-learning/lessons/lesson.source.json", "json": source}]}, home_dir=self.home)
        path = self.root / ".session-learning/lessons" / (survivor["id"] + ".json")
        stored = json.loads(path.read_text())
        source_stored = json.loads((path.parent / "lesson.source.json").read_text())
        patch = {"expected_sha256": e.canonical_record_sha256(stored), "intent": "replace_action", "operations": [
            {"op": "replace_safe_path", "value": stored["safe_path"]},
            {"op": "append_provenance", "value": source["provenance"]},
            {"op": "append_exception", "value": source["exceptions"]},
            {"op": "append_relationship", "value": [{"type": "supersedes", "lesson_id": source["id"]}]}]}
        changes = [{"path": f".session-learning/lessons/{stored['id']}.json", "lesson_patch": patch},
            {"path": ".session-learning/lessons/lesson.source.json", "lesson_patch": {
                "expected_sha256": e.canonical_record_sha256(source_stored), "intent": "supersede", "operations": [
                    {"op": "set_status", "value": "superseded"}, {"op": "set_delivery_none"}]}}]
        with self.assertRaisesRegex(ValueError, "does not permit"):
            e.apply_manifest(self.root, {"manifest_schema_version": 2, "origin": "maintenance", "changes": changes}, home_dir=self.home)
        e.apply_manifest(self.root, self.maintenance(changes), home_dir=self.home)
        combined = json.loads(path.read_text())
        self.assertEqual(source["exceptions"], combined["exceptions"])
        self.assertIn(source["provenance"][0], combined["provenance"])
        self.assertEqual(stored["usage"], combined["usage"])
        self.assertEqual([], e.validate_store(self.root, home_dir=self.home))

    def test_content_dedupe_ignores_json_object_key_order(self):
        self.enabled()
        value = draft()
        first = x.save_draft(e, self.root, value, home=self.home)
        reordered = json.loads(json.dumps(value, sort_keys=True))
        outcome = x.save_draft(e, self.root, reordered, home=self.home)
        self.assertEqual(first["id"], outcome["id"])
        self.assertEqual("duplicate", outcome["reason"])
        self.assertEqual(1, x.pending(e, self.root, home=self.home)["total"])

    def test_manual_configuration_with_utf8_bom_and_day_rollover(self):
        report = self.enabled()
        private = Path(report["changed_file"])
        private.write_text(private.read_text(), encoding="utf-8-sig")
        self.assertTrue(e._load_config(self.root, self.home)["drafting_enabled"])
        self.hook("SessionStart", source="startup")
        state_path = e._state_path(self.data, self.root, "session-one")
        state = x.read_json(state_path)
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        state["activity_date"] = yesterday
        state_path.write_text(json.dumps(state))
        self.hook()
        aggregate = x.read_json(x.activity_file(e, self.root, self.data, yesterday))
        self.assertEqual(1, aggregate["counts"]["hook_events"])
        self.assertEqual(2, x.activity(e, self.root, home=self.home, data_dir=self.data)["counts"]["hook_events"])

    def test_activity_details_are_bounded_and_malformed_state_cannot_leak_content(self):
        identities = {f"project:lesson.{i:03}": i + 1 for i in range(25)}
        identities[str(self.root)] = 1
        x.add_activity(e, self.root, {"hook_events": 3, "raw prompt content": 1}, home=self.home, data_dir=self.data, lessons=identities)
        first = x.activity(e, self.root, home=self.home, data_dir=self.data)
        self.assertEqual(20, len(first["lesson_emissions"]))
        self.assertEqual(25, first["total_lesson_identities"])
        self.assertEqual(5, len(x.activity(e, self.root, home=self.home, data_dir=self.data, lesson_page=2)["lesson_emissions"]))
        self.assertNotIn("raw prompt content", json.dumps(first))
        self.assertNotIn(str(self.root), json.dumps(first))

    def test_receipt_audit_and_key_order_independent_replay(self):
        self.seed()
        proof = evidence()
        proof["id"] = "evidence.receipt"
        manifest = {"manifest_schema_version": 3, "operation_id": "operation.receipt", "origin": "current_session", "changes": [
            {"path": ".session-learning/evidence/evidence.receipt.json", "json": proof}]}
        e.apply_manifest(self.root, manifest, home_dir=self.home)
        self.assertTrue(e.apply_manifest(self.root, json.loads(json.dumps(manifest, sort_keys=True)), home_dir=self.home)["replayed"])
        receipt = x.receipt_path(e, self.root, "project", "operation.receipt", self.home)
        receipt.write_text(json.dumps({"schema_version": 1}))
        self.assertTrue(any("receipt" in error for error in e.audit_store(self.root, home_dir=self.home)["validation_errors"]))
        with self.assertRaisesRegex(ValueError, "receipt schema"):
            e.apply_manifest(self.root, manifest, home_dir=self.home)

    def test_receipts_cannot_commit_without_canonical_ids(self):
        self.seed()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "canonical resulting IDs"):
            e.apply_manifest(self.root, {"manifest_schema_version": 3, "origin": "current_session",
                "operation_id": "accept.empty", "changes": [{"path": "AGENTS.md", "content": "A proposed instruction.\n"}]}, home_dir=self.home)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_local_snapshot_includes_relevant_project_instructions(self):
        self.seed(authority="local")
        context = x.reflection_context(e, self.root, home=self.home)
        (self.root / "AGENTS.md").write_text("Different always-visible project convention.")
        self.assertNotEqual(context["revisions"]["local"], x.store_revision(e, self.root, "local", self.home))


if __name__ == "__main__":
    unittest.main()
