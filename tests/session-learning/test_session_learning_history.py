from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


def find_repo_root(start: Path) -> Path:
    for parent in start.resolve().parents:
        if (parent / "plugins" / "mullans-productivity" / "skills").is_dir():
            return parent
    raise RuntimeError(f"Unable to find repository root from {start}")


REPO_ROOT = find_repo_root(Path(__file__))
SKILL_ROOT = REPO_ROOT / "plugins" / "mullans-productivity" / "skills" / "session-learning"
HISTORY_SCRIPT = SKILL_ROOT / "scripts" / "session_learning_history.py"
SESSION_SCRIPT = SKILL_ROOT / "scripts" / "session_learning.py"
sys.dont_write_bytecode = True


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


history = load_module("session_learning_history", HISTORY_SCRIPT)
session_learning = load_module("session_learning_for_history", SESSION_SCRIPT)


def event(
    event_id: str,
    ordinal: int,
    *,
    operation: str = "run_command",
    strategy: str = "direct",
    targets: tuple[str, ...] = ("src/widget.py",),
    resources: tuple[str, ...] = (),
    fingerprint: str | None = None,
    outcome: str = "unknown",
    failure_class: str | None = None,
    diagnostic_code: str | None = None,
    kind: str = "operation",
    session_id: str = "session-1",
):
    compact_fingerprint = hashlib.sha256(
        (fingerprint or f"fp-{event_id}").encode("utf-8")
    ).hexdigest()
    return history.NormalizedEvent(
        session_id=session_id,
        event_id=event_id,
        timestamp=None,
        ordinal=ordinal,
        kind=kind,
        operation=operation,
        strategy=strategy,
        targets=targets,
        resources=resources,
        input_fingerprint=compact_fingerprint,
        outcome=outcome,
        failure_class=failure_class,
        diagnostic_code=diagnostic_code,
    )


def recovery_events(*, repair_strategy: str = "corrected_command") -> list[object]:
    return [
        event(
            "failure",
            1,
            strategy="direct",
            fingerprint="before",
            outcome="failure",
            failure_class="invocation",
            diagnostic_code="command_failed",
        ),
        event(
            "repair",
            2,
            strategy=repair_strategy,
            fingerprint="after",
            outcome="success",
        ),
        event(
            "verification",
            3,
            operation="run_command",
            strategy="targeted",
            fingerprint="verify",
            outcome="success",
        ),
    ]


class NormalizationTests(unittest.TestCase):
    def test_normalize_event_keeps_only_bounded_normalized_structure(self) -> None:
        normalized = history.normalize_event(
            {
                "session_id": "session-1",
                "event_id": "evt-1",
                "ordinal": 1,
                "kind": "operation",
                "operation": "RUN COMMAND",
                "strategy": "Corrected Command",
                "targets": [r"C:\Code\project\src\Widget.py"],
                "resources": [r"C:\Users\Sean\.cache\input.json"],
                "input": {"command": "tool --token=super-secret-value"},
                "outcome": "failure",
                "failure_class": "invocation",
                "diagnostic_code": "command_failed",
            },
            project_root=r"C:\Code\project",
            home_dir=r"C:\Users\Sean",
        )

        self.assertEqual(normalized.operation, "run_command")
        self.assertEqual(normalized.strategy, "corrected_command")
        self.assertEqual(normalized.targets, ("<project>/src/widget.py",))
        self.assertEqual(normalized.resources, ("<home>/.cache/input.json",))
        self.assertRegex(normalized.input_fingerprint, r"^[0-9a-f]{64}$")
        self.assertNotIn("super-secret-value", repr(normalized))

    def test_normalized_event_has_no_public_serializer(self) -> None:
        normalized = event("evt", 1)

        self.assertFalse(hasattr(normalized, "to_dict"))
        self.assertFalse(hasattr(normalized, "to_json"))

    def test_unsupported_consequential_record_is_a_degrading_barrier(self) -> None:
        result = history.mine_recoveries(
            [
                recovery_events()[0],
                {"kind": "operation", "event_id": "truncated", "truncated": True},
                *recovery_events()[1:],
            ]
        )

        self.assertTrue(result.degraded)
        self.assertEqual(result.candidates, ())
        self.assertEqual(result.barrier_ids, ("truncated",))

    def test_allowlisted_inert_unknown_is_skipped_without_degradation(self) -> None:
        values = recovery_events()
        result = history.mine_recoveries(
            [values[0], {"kind": "heartbeat", "event_id": "pulse"}, *values[1:]]
        )

        self.assertFalse(result.degraded)
        self.assertEqual(len(result.candidates), 1)

    def test_normalizes_and_redacts_nested_input_before_fingerprinting(self) -> None:
        raw_dumps = json.dumps
        record = {
            "session_id": "session-1",
            "event_id": "evt-1",
            "ordinal": 1,
            "kind": "operation",
            "operation": "run_command",
            "strategy": "direct",
            "targets": ["src/widget.py"],
            "resources": [],
            "input": {
                "command": "deploy --token=ghp_abcdefghijklmnopqrstuvwxyz123456",
                "nested": {"password": "correct-horse-battery-staple"},
            },
            "outcome": "failure",
            "failure_class": "invocation",
            "diagnostic_code": "command_failed",
        }
        with mock.patch.object(history.json, "dumps", wraps=raw_dumps) as dumps:
            history.normalize_event(record)

        serialized_values = [raw_dumps(call.args[0], sort_keys=True) for call in dumps.call_args_list]
        fingerprint_input = next(value for value in serialized_values if '"input"' in value)
        self.assertNotIn("ghp_", fingerprint_input)
        self.assertNotIn("correct-horse-battery-staple", fingerprint_input)

    def test_rejects_oversized_ids_and_aggregate_normalized_events(self) -> None:
        base = {
            "session_id": "session-1",
            "event_id": "evt-1",
            "ordinal": 1,
            "kind": "operation",
            "operation": "run_command",
            "strategy": "direct",
            "targets": ["src/widget.py"],
            "resources": [],
            "input": {},
            "outcome": "failure",
            "failure_class": "invocation",
            "diagnostic_code": "command_failed",
        }
        with self.assertRaises(history.HistoryRecordError):
            history.normalize_event({**base, "event_id": "e" * 121})
        with self.assertRaises(history.HistoryRecordError):
            history.normalize_event(
                {
                    **base,
                    "targets": [
                        f"src/{chr(97 + index)}/{'segment-' * 28}" for index in range(8)
                    ],
                }
            )

    def test_consequential_fields_make_inert_label_a_barrier(self) -> None:
        values = recovery_events()
        disguised = {
            "kind": "heartbeat",
            "event_id": "disguised",
            "operation": "run_command",
            "truncated": True,
        }

        result = history.mine_recoveries([values[0], disguised, *values[1:]])

        self.assertTrue(result.degraded)
        self.assertEqual(result.candidates, ())

    def test_unsafe_preconstructed_event_is_a_barrier(self) -> None:
        failure, _, _ = recovery_events()
        unsafe = event(
            "unsafe\nevent",
            2,
            operation="read_file",
            strategy="targeted",
            outcome="success",
        )
        repair = event("repair", 3, strategy="corrected_command", outcome="success")
        verification = event(
            "verification", 4, operation="run_command", strategy="targeted", outcome="success"
        )

        result = history.mine_recoveries([failure, unsafe, repair, verification])

        self.assertTrue(result.degraded)
        self.assertEqual(result.candidates, ())

    def test_posix_relative_paths_preserve_case_and_do_not_false_pair(self) -> None:
        def raw(event_id: str, ordinal: int, target: str, strategy: str, outcome: str):
            return {
                "session_id": "session-1",
                "event_id": event_id,
                "ordinal": ordinal,
                "kind": "operation",
                "operation": "run_command",
                "strategy": strategy,
                "targets": [target],
                "resources": [],
                "input": {"command": event_id},
                "outcome": outcome,
                "failure_class": "invocation" if outcome == "failure" else None,
                "diagnostic_code": "command_failed" if outcome == "failure" else None,
            }

        records = [
            raw("failure", 1, "src/Widget.py", "direct", "failure"),
            raw("repair", 2, "src/widget.py", "corrected_path", "success"),
            raw("verification", 3, "src/widget.py", "targeted", "success"),
        ]

        self.assertEqual(history.normalize_event(records[0]).targets, ("src/Widget.py",))
        self.assertEqual(history.mine_recoveries(records).candidates, ())

    def test_arbitrary_posix_absolute_targets_are_redacted_but_urls_are_not_paths(self) -> None:
        base = {
            "session_id": "session-1",
            "event_id": "evt-1",
            "ordinal": 1,
            "kind": "operation",
            "operation": "fetch",
            "strategy": "direct",
            "resources": [],
            "input": {},
            "outcome": "success",
        }
        for target in ("/tmp/Build/secret.txt", "/var/log/app.log", "/opt/Tool/config"):
            with self.subTest(target=target):
                normalized = history.normalize_event({**base, "targets": [target]})
                self.assertEqual(normalized.targets, ("<path>",))
        normalized_url = history.normalize_event(
            {**base, "event_id": "evt-url", "targets": ["https://example.com/A/B"]}
        )
        self.assertEqual(normalized_url.targets, ("https://example.com/A/B",))


class RecoveryMatchingTests(unittest.TestCase):
    def test_mines_corrected_operation_with_later_verification(self) -> None:
        result = history.mine_recoveries(recovery_events())

        self.assertFalse(result.degraded)
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.failure_id, "failure")
        self.assertEqual(candidate.repair_ids, ("repair",))
        self.assertEqual(candidate.verification_id, "verification")
        self.assertEqual(candidate.supporting_ids, ())
        self.assertEqual(candidate.behavior_delta["type"], "replace")

    def test_accepts_supported_semantic_repair_strategies(self) -> None:
        for strategy in (
            "corrected_command",
            "corrected_path",
            "narrowed_scope",
            "escalated_permission",
            "correct_tool_convention",
            "chunked_resource",
            "changed_retry_strategy",
            "reordered_workflow",
        ):
            with self.subTest(strategy=strategy):
                self.assertEqual(len(history.mine_recoveries(recovery_events(repair_strategy=strategy)).candidates), 1)

    def test_reordered_workflow_delta_never_invents_unobserved_steps(self) -> None:
        candidate = history.mine_recoveries(
            recovery_events(repair_strategy="reordered_workflow")
        ).candidates[0]

        self.assertEqual(
            candidate.behavior_delta,
            {
                "type": "replace",
                "before": [{"operation": "run_command", "strategy": "direct"}],
                "after": [
                    {"operation": "run_command", "strategy": "reordered_workflow"}
                ],
            },
        )

    def test_collects_up_to_three_repairs_and_four_supporting_events(self) -> None:
        values = recovery_events()
        repairs = [
            event(
                "repair-1",
                2,
                strategy="corrected_command",
                fingerprint="r1",
                outcome="success",
            ),
            event("repair-2", 4, strategy="corrected_path", fingerprint="r2", outcome="success"),
        ]
        support = event(
            "support",
            3,
            operation="read_file",
            strategy="targeted",
            fingerprint="s1",
            outcome="success",
        )
        verification = event(
            "verification", 5, operation="run_command", strategy="targeted", outcome="success"
        )

        candidate = history.mine_recoveries([values[0], repairs[0], support, repairs[1], verification]).candidates[0]

        self.assertEqual(candidate.repair_ids, ("repair-1", "repair-2"))
        self.assertEqual(candidate.supporting_ids, ("support",))

    def test_preserves_complete_candidates_across_later_barrier(self) -> None:
        result = history.mine_recoveries(
            [*recovery_events(), {"kind": "operation", "event_id": "bad", "truncated": True}]
        )

        self.assertTrue(result.degraded)
        self.assertEqual(len(result.candidates), 1)

    def test_user_boundary_resets_pending_correlation(self) -> None:
        values = recovery_events()
        boundary = event("boundary", 2, kind="user_boundary", operation="", strategy="")

        result = history.mine_recoveries([values[0], boundary, *values[1:]])

        self.assertEqual(result.candidates, ())

    def test_rejects_unrelated_success_and_incompatible_target(self) -> None:
        failure, repair, verification = recovery_events()
        unrelated = event(
            "unrelated",
            2,
            operation="write_file",
            strategy="corrected_path",
            targets=("docs/readme.md",),
            outcome="success",
        )
        incompatible = event(
            "incompatible",
            2,
            strategy="corrected_path",
            targets=("src/other.py",),
            outcome="success",
        )

        self.assertEqual(history.mine_recoveries([failure, unrelated, verification]).candidates, ())
        self.assertEqual(history.mine_recoveries([failure, incompatible, verification]).candidates, ())

    def test_rejects_identical_transient_retry_and_unknown_verification(self) -> None:
        failure, _, verification = recovery_events()
        identical = event(
            "identical", 2, strategy="direct", fingerprint="before", outcome="success"
        )
        unknown_verification = event(
            "verification", 3, operation="run_command", strategy="targeted", outcome="unknown"
        )

        self.assertEqual(history.mine_recoveries([failure, identical, verification]).candidates, ())
        self.assertEqual(
            history.mine_recoveries([failure, recovery_events()[1], unknown_verification]).candidates,
            (),
        )

    def test_rejects_probing_or_expected_failure(self) -> None:
        for failure_class in ("probe", "expected"):
            with self.subTest(failure_class=failure_class):
                values = recovery_events()
                values[0] = event(
                    "failure",
                    1,
                    outcome="failure",
                    failure_class=failure_class,
                    diagnostic_code="command_failed",
                )
                self.assertEqual(history.mine_recoveries(values).candidates, ())

    def test_dependency_install_is_a_stronger_intervening_explanation(self) -> None:
        failure, repair, verification = recovery_events()
        install = event(
            "install",
            2,
            operation="install_dependency",
            strategy="dependency_install",
            resources=("package",),
            targets=("src/widget.py",),
            outcome="success",
        )
        repair = event(
            "repair", 3, strategy="corrected_command", fingerprint="after", outcome="success"
        )
        verification = event(
            "verification", 4, operation="run_command", strategy="targeted", outcome="success"
        )

        self.assertEqual(history.mine_recoveries([failure, install, repair, verification]).candidates, ())

    def test_rejects_recovery_outside_bounded_proximity(self) -> None:
        failure, repair, verification = recovery_events()
        repair = event("repair", 20, strategy="corrected_command", outcome="success")
        verification = event(
            "verification", 21, operation="run_command", strategy="targeted", outcome="success"
        )

        self.assertEqual(history.mine_recoveries([failure, repair, verification]).candidates, ())

    def test_requires_the_same_operation_not_only_the_same_family(self) -> None:
        failure, _, verification = recovery_events()
        family_only = event(
            "repair",
            2,
            operation="retry",
            strategy="changed_retry_strategy",
            outcome="success",
        )

        self.assertEqual(
            history.mine_recoveries([failure, family_only, verification]).candidates, ()
        )

    def test_requires_targets_and_resources_to_correspond_by_channel(self) -> None:
        failure, _, verification = recovery_events()
        crossed_identity = event(
            "repair",
            2,
            strategy="corrected_path",
            targets=(),
            resources=("src/widget.py",),
            outcome="success",
        )

        self.assertEqual(
            history.mine_recoveries([failure, crossed_identity, verification]).candidates,
            (),
        )

    def test_unknown_outcome_is_not_a_repair(self) -> None:
        failure, _, verification = recovery_events()
        repair = event(
            "repair", 2, strategy="corrected_command", fingerprint="after", outcome="unknown"
        )

        self.assertEqual(history.mine_recoveries([failure, repair, verification]).candidates, ())

    def test_verification_must_match_the_exact_repaired_operation(self) -> None:
        failure, repair, _ = recovery_events()
        family_only_verification = event(
            "verification",
            3,
            operation="retry",
            strategy="targeted",
            outcome="success",
        )

        self.assertEqual(
            history.mine_recoveries([failure, repair, family_only_verification]).candidates,
            (),
        )


class CandidateValidationTests(unittest.TestCase):
    def candidate(self, **overrides: object):
        values: dict[str, object] = {
            "session_id": "session-1",
            "failure_id": "failure",
            "repair_ids": ("repair",),
            "verification_id": "verification",
            "supporting_ids": (),
            "behavior_delta": {
                "type": "replace",
                "before": [{"operation": "run_command", "strategy": "direct"}],
                "after": [{"operation": "run_command", "strategy": "corrected_command"}],
            },
            "contrast": "run_command/direct -> run_command/corrected_command; command failed",
            "source_fingerprint": "a" * 64,
            "content_fingerprint": "b" * 64,
            "analyzer_version": "1.0",
        }
        values.update(overrides)
        return history.RecoveryCandidate(**values)

    def test_validates_exact_causal_slice_roles_and_order(self) -> None:
        events = {item.event_id: item for item in recovery_events()}
        candidate = self.candidate()

        self.assertEqual(history.validate_recovery_candidate(candidate, events), [])

        invalid = self.candidate(repair_ids=("failure", "repair"), supporting_ids=("repair",))
        errors = history.validate_recovery_candidate(invalid, events)
        self.assertTrue(any("unique" in error for error in errors))

    def test_rejects_cross_session_or_misordered_slice(self) -> None:
        values = recovery_events()
        values[1] = event("repair", 4, session_id="session-2")
        values[2] = event("verification", 3, operation="run_command", outcome="success")
        events = {item.event_id: item for item in values}

        errors = history.validate_recovery_candidate(self.candidate(), events)

        self.assertTrue(any("same session" in error for error in errors))
        self.assertTrue(any("ordered" in error for error in errors))

    def test_behavior_delta_enforces_type_and_step_invariants(self) -> None:
        valid = {
            "type": "reorder",
            "before": [
                {"operation": "write_file", "strategy": "direct"},
                {"operation": "verify", "strategy": "targeted"},
            ],
            "after": [
                {"operation": "verify", "strategy": "targeted"},
                {"operation": "write_file", "strategy": "direct"},
            ],
        }
        self.assertEqual(history.validate_behavior_delta(valid), [])

        invalid_values = (
            {"type": "add", "before": [{"operation": "verify", "strategy": "targeted"}], "after": []},
            {"type": "remove", "before": [], "after": [{"operation": "verify", "strategy": "targeted"}]},
            {"type": "replace", "before": [], "after": []},
            {"type": "reorder", "before": [{"operation": "verify", "strategy": "targeted"}], "after": [{"operation": "verify", "strategy": "targeted"}]},
            {"type": "replace", "before": [{"operation": "SHELL", "strategy": "raw transcript"}], "after": [{"operation": "verify", "strategy": "targeted"}]},
        )
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertTrue(history.validate_behavior_delta(value))

    def test_contrast_is_bounded_and_redacts_sensitive_values(self) -> None:
        failure, repair, _ = recovery_events()
        failure = event(
            "failure",
            1,
            targets=(r"C:\Users\Sean\project\secret.py", "person@example.com", "ghp_abcdefghijklmnopqrstuvwxyz123456"),
            outcome="failure",
            failure_class="invocation",
            diagnostic_code="permission_denied",
        )
        repair = event(
            "repair",
            2,
            strategy="escalated_permission",
            targets=(r"C:\Users\Sean\project\secret.py",),
            outcome="success",
        )

        contrast = history.build_compact_contrast(failure, (repair,))

        self.assertLessEqual(len(contrast), 500)
        self.assertNotIn("Sean", contrast)
        self.assertNotIn("person@example.com", contrast)
        self.assertNotIn("ghp_", contrast)
        self.assertIn("permission denied", contrast)

    def test_semantic_validation_checks_failure_repairs_and_verification(self) -> None:
        cases = []
        invalid_failure = recovery_events()
        invalid_failure[0] = event("failure", 1, outcome="unknown")
        cases.append(invalid_failure)
        invalid_repair = recovery_events()
        invalid_repair[1] = event(
            "repair", 2, operation="retry", strategy="changed_retry_strategy", outcome="success"
        )
        cases.append(invalid_repair)
        invalid_verification = recovery_events()
        invalid_verification[2] = event(
            "verification", 3, operation="run_command", strategy="targeted", outcome="unknown"
        )
        cases.append(invalid_verification)

        for values in cases:
            with self.subTest(values=values):
                errors = history.validate_recovery_candidate(
                    self.candidate(), {item.event_id: item for item in values}
                )
                self.assertTrue(any("semantic" in error for error in errors))

    def test_semantic_validation_allows_shared_repair_ordinals(self) -> None:
        failure, repair, verification = recovery_events()
        repair_two = event(
            "repair-2", 2, strategy="corrected_path", fingerprint="later", outcome="success"
        )
        candidate = self.candidate(repair_ids=("repair", "repair-2"))
        values = {item.event_id: item for item in (failure, repair, repair_two, verification)}

        self.assertEqual(history.validate_recovery_candidate(candidate, values), [])

    def test_malformed_candidate_ids_return_errors_instead_of_raising(self) -> None:
        malformed = self.candidate(repair_ids=(["not-hashable"],))

        errors = history.validate_recovery_candidate(malformed, {})

        self.assertTrue(any("IDs" in error for error in errors))

    def test_candidate_validation_caps_ids_and_aggregate_size(self) -> None:
        failure, repair, verification = recovery_events()
        events = {item.event_id: item for item in (failure, repair, verification)}
        oversized = self.candidate(session_id="s" * 121, contrast="x" * 500)

        errors = history.validate_recovery_candidate(oversized, events)

        self.assertTrue(any("session_id" in error for error in errors))

    def test_candidate_validation_accepts_uuid_ids_but_rejects_unsafe_grammar(self) -> None:
        session_id = "123e4567-e89b-12d3-a456-426614174000"
        ids = (
            "123e4567-e89b-12d3-a456-426614174001",
            "123e4567-e89b-12d3-a456-426614174002",
            "123e4567-e89b-12d3-a456-426614174003",
        )
        values = [
            event(ids[0], 1, session_id=session_id, outcome="failure", failure_class="invocation", diagnostic_code="command_failed"),
            event(ids[1], 2, session_id=session_id, strategy="corrected_command", outcome="success"),
            event(ids[2], 3, session_id=session_id, strategy="targeted", outcome="success"),
        ]
        candidate = self.candidate(
            session_id=session_id,
            failure_id=ids[0],
            repair_ids=(ids[1],),
            verification_id=ids[2],
        )
        self.assertEqual(
            history.validate_recovery_candidate(
                candidate, {item.event_id: item for item in values}
            ),
            [],
        )

        unsafe = self.candidate(session_id="session id with spaces")
        errors = history.validate_recovery_candidate(
            unsafe, {item.event_id: item for item in recovery_events()}
        )
        self.assertTrue(any("session_id" in error for error in errors))

    def test_candidate_fingerprints_are_type_checked_without_crashing(self) -> None:
        events = {item.event_id: item for item in recovery_events()}
        for field in ("source_fingerprint", "content_fingerprint"):
            with self.subTest(field=field):
                try:
                    errors = history.validate_recovery_candidate(
                        self.candidate(**{field: None}), events
                    )
                except (TypeError, AttributeError) as exc:
                    self.fail(f"fingerprint validation raised {type(exc).__name__}: {exc}")
                self.assertTrue(any("fingerprints" in error for error in errors))


class RecoveryEvidenceValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def record(self) -> dict[str, object]:
        record: dict[str, object] = {
            "schema_version": 2,
            "record_type": "evidence",
            "id": "pending",
            "authority": "project",
            "session_id": "session-1",
            "signal": "recovery_pair",
            "situation": "A targeted command failed.",
            "attempted_behavior": "Used the direct invocation strategy.",
            "feedback": "The normalized diagnostic was command failed.",
            "corrected_behavior": "Used the corrected command strategy.",
            "outcome": "Targeted verification succeeded.",
            "created_at": "2026-09-09T12:00:00Z",
            "source": {
                "host": "codex",
                "failure_event_id": "failure",
                "repair_event_ids": ["repair"],
                "verification_event_id": "verification",
                "supporting_event_ids": [],
                "source_fingerprint": "0" * 64,
                "content_fingerprint": "0" * 64,
                "analyzer_version": "1.0",
            },
            "behavior_delta": {
                "type": "replace",
                "before": [{"operation": "run_command", "strategy": "direct"}],
                "after": [{"operation": "run_command", "strategy": "corrected_command"}],
            },
        }
        source = record["source"]
        assert isinstance(source, dict)
        source_fingerprint = session_learning._source_fingerprint(
            source["host"], record["session_id"],
            source["failure_event_id"], source["verification_event_id"],
        )
        source["source_fingerprint"] = source_fingerprint
        source["content_fingerprint"] = session_learning._content_fingerprint(
            record["feedback"], session_learning._source_roles(source), record["behavior_delta"]
        )
        record["id"] = f"evidence.recovery.{source_fingerprint[:20]}"
        return record

    def write(self, value: dict[str, object]) -> None:
        target = self.root / ".agents" / "learning" / "evidence" / f"{value['id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def test_accepts_complete_recovery_pair_evidence(self) -> None:
        self.write(self.record())

        errors = session_learning.validate_store(self.root)

        self.assertEqual(errors, [])

    def test_rejects_recovery_pair_without_source_or_behavior_delta(self) -> None:
        value = self.record()
        del value["source"]
        del value["behavior_delta"]
        self.write(value)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("source" in error for error in errors))
        self.assertTrue(any("behavior_delta" in error for error in errors))

    def test_rejects_invalid_source_cardinality_and_delta(self) -> None:
        value = self.record()
        value["source"]["repair_event_ids"] = []  # type: ignore[index]
        value["source"]["supporting_event_ids"] = ["a", "b", "c", "d", "e"]  # type: ignore[index]
        value["behavior_delta"] = {
            "type": "replace",
            "before": [],
            "after": [{"operation": "run_command", "strategy": "corrected_command"}],
        }
        self.write(value)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("repair_event_ids" in error for error in errors))
        self.assertTrue(any("supporting_event_ids" in error for error in errors))
        self.assertTrue(any("behavior_delta" in error for error in errors))

    def test_rejects_oversized_recovery_evidence_fields_and_aggregate(self) -> None:
        value = self.record()
        value["situation"] = "x" * 501
        value["source"]["failure_event_id"] = "f" * 121  # type: ignore[index]
        self.write(value)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("situation" in error and "500" in error for error in errors))
        self.assertTrue(any("failure_event_id" in error and "120" in error for error in errors))

    def test_rejects_recovery_evidence_with_unbounded_total_payload(self) -> None:
        value = self.record()
        for field in ("situation", "attempted_behavior", "feedback", "corrected_behavior", "outcome"):
            value[field] = field + ("x" * 490)
        self.write(value)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("recovery_pair evidence" in error and "2500" in error for error in errors))

    def test_rejects_raw_project_or_home_paths_in_recovery_evidence(self) -> None:
        for raw_path in (
            str(self.root / "src" / "widget.py"),
            r"C:\Users\Sean\project\src\widget.py",
            "/home/sean/project/src/widget.py",
            "/tmp/project/src/widget.py",
            "/var/lib/project/state.json",
            "/opt/tool/config.json",
        ):
            with self.subTest(raw_path=raw_path):
                value = self.record()
                value["situation"] = f"Failure at {raw_path}"
                self.write(value)

                errors = session_learning.validate_store(self.root)

                self.assertTrue(any("normalized and redacted" in error for error in errors))

    def test_rejects_high_entropy_prose_but_allows_opaque_source_ids(self) -> None:
        value = self.record()
        value["feedback"] = "Observed aZ9_qP4LmN7xR2vK8sT5wY1cD6fH3jB0 secret-like value."
        value["source"]["failure_event_id"] = "evt-aZ9_qP4LmN7xR2vK8sT5wY1cD6fH3jB0"  # type: ignore[index]
        self.write(value)

        errors = session_learning.validate_store(self.root)

        self.assertTrue(any("feedback" in error and "normalized and redacted" in error for error in errors))
        self.assertFalse(any("failure_event_id" in error and "normalized and redacted" in error for error in errors))

    def test_accepts_uuid_session_and_event_ids_in_recovery_evidence(self) -> None:
        value = self.record()
        value["session_id"] = "123e4567-e89b-12d3-a456-426614174000"
        value["source"]["failure_event_id"] = "123e4567-e89b-12d3-a456-426614174001"  # type: ignore[index]
        value["source"]["repair_event_ids"] = ["123e4567-e89b-12d3-a456-426614174002"]  # type: ignore[index]
        value["source"]["verification_event_id"] = "123e4567-e89b-12d3-a456-426614174003"  # type: ignore[index]
        source = value["source"]
        assert isinstance(source, dict)
        source_fingerprint = session_learning._source_fingerprint(
            source["host"], value["session_id"],
            source["failure_event_id"], source["verification_event_id"],
        )
        source["source_fingerprint"] = source_fingerprint
        source["content_fingerprint"] = session_learning._content_fingerprint(
            value["feedback"], session_learning._source_roles(source), value["behavior_delta"]
        )
        value["id"] = f"evidence.recovery.{source_fingerprint[:20]}"
        self.write(value)

        self.assertEqual(session_learning.validate_store(self.root), [])

    def test_noncredentialed_urls_are_not_rejected_as_absolute_paths(self) -> None:
        value = self.record()
        value["situation"] = "Fetched https://example.com/A/B for verification."
        self.write(value)

        self.assertEqual(session_learning.validate_store(self.root), [])


class CodexHistoryScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.root = self.base / "repo"
        self.root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_session(
        self, session_id: str, cwd: Path, records: list[object], *, archived: bool = False
    ) -> Path:
        folder = self.home / ".codex" / ("archived_sessions" if archived else "sessions")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{session_id}.jsonl"
        lines = [
            {
                "type": "session_meta",
                "timestamp": "2026-09-09T12:00:00Z",
                "payload": {"id": session_id, "cwd": str(cwd)},
            },
            *records,
        ]
        path.write_text("".join(json.dumps(item) + "\n" for item in lines), encoding="utf-8")
        return path

    @staticmethod
    def normalized_records(session_id: str) -> list[dict[str, object]]:
        return [
            {
                "kind": "operation", "session_id": session_id, "event_id": "failure",
                "ordinal": 1, "operation": "run_command", "strategy": "direct",
                "targets": ["src/widget.py"], "resources": [], "input": {"args": "old"},
                "outcome": "failure", "failure_class": "invocation",
                "diagnostic_code": "command_failed",
            },
            {
                "kind": "operation", "session_id": session_id, "event_id": "repair",
                "ordinal": 2, "operation": "run_command", "strategy": "corrected_command",
                "targets": ["src/widget.py"], "resources": [], "input": {"args": "new"},
                "outcome": "success", "failure_class": None, "diagnostic_code": None,
            },
            {
                "kind": "operation", "session_id": session_id, "event_id": "verification",
                "ordinal": 3, "operation": "run_command", "strategy": "targeted",
                "targets": ["src/widget.py"], "resources": [], "input": {"args": "verify"},
                "outcome": "success", "failure_class": None, "diagnostic_code": None,
            },
        ]

    def test_missing_history_roots_is_failed_and_read_only(self) -> None:
        before = sorted(str(path) for path in self.base.rglob("*"))
        scan = history.CodexSessionScanner().scan(self.root, home_dir=self.home)
        self.assertEqual("failed", scan.status)
        self.assertEqual(before, sorted(str(path) for path in self.base.rglob("*")))

    def test_matches_root_and_descendant_but_rejects_parent_and_sibling(self) -> None:
        (self.root / "src").mkdir()
        sibling = self.base / "sibling"
        sibling.mkdir()
        self.write_session("root-session", self.root, self.normalized_records("root-session"))
        self.write_session("nested-session", self.root / "src", self.normalized_records("nested-session"))
        self.write_session("parent-session", self.base, self.normalized_records("parent-session"))
        self.write_session("sibling-session", sibling, self.normalized_records("sibling-session"))
        scan = history.CodexSessionScanner().scan(self.root, home_dir=self.home)
        self.assertEqual("complete", scan.status)
        self.assertEqual(2, scan.selected_sessions)
        self.assertEqual(2, len(scan.candidates))

    def test_malformed_line_is_a_degraded_barrier_without_losing_prior_candidate(self) -> None:
        path = self.write_session(
            "session-1", self.root, self.normalized_records("session-1")
        )
        with path.open("a", encoding="utf-8") as stream:
            stream.write("{malformed\n")
        scan = history.CodexSessionScanner().scan(self.root, home_dir=self.home)
        self.assertEqual("degraded", scan.status)
        self.assertEqual(1, len(scan.candidates))
        self.assertTrue(any(item.code == "causal_barrier" for item in scan.diagnostics))

    def test_source_identity_ignores_repair_interpretation(self) -> None:
        first = history.mine_recoveries(recovery_events()).candidates[0]
        second_events = recovery_events(repair_strategy="changed_arguments")
        second = history.mine_recoveries(second_events).candidates[0]
        self.assertEqual(first.source_fingerprint, second.source_fingerprint)
        self.assertNotEqual(first.content_fingerprint, second.content_fingerprint)

    def test_compact_and_detail_reports_agree_and_hide_unchanged_bodies(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        scan = history.CodexSessionScanner().scan(self.root, home_dir=self.home)
        candidate = scan.candidates[0]
        compact = history.render_scan_report(scan)
        detail = history.render_scan_report(scan, detail_id=history.candidate_id(candidate))
        self.assertEqual(compact["candidates"][0]["id"], detail["candidate"]["id"])
        unchanged = history.render_scan_report(
            scan, classifications={candidate.source_fingerprint: "unchanged"}
        )
        self.assertEqual([], unchanged["candidates"])
        self.assertEqual(1, unchanged["counts"]["unchanged"])

    def test_continuation_refuses_changed_scan_fingerprint(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        with self.assertRaisesRegex(ValueError, "scan fingerprint changed"):
            session_learning.mine_history(
                self.root, home_dir=self.home, expect_scan="0" * 64
            )

    def test_requested_session_not_found_is_failed(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        scan = history.CodexSessionScanner().scan(
            self.root, home_dir=self.home, session_id="missing-session"
        )
        self.assertEqual("failed", scan.status)
        self.assertEqual(0, scan.selected_sessions)

    def test_deadline_exhaustion_is_degraded_even_without_candidates(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        ticks = iter((0.0, 31.0, 31.0, 31.0))
        budget = history.ScanBudget(clock=lambda: next(ticks), deadline_seconds=30.0)
        scan = history.CodexSessionScanner().scan(
            self.root, home_dir=self.home, budget=budget
        )
        self.assertEqual("degraded", scan.status)
        self.assertEqual((), scan.candidates)
        self.assertTrue(any(item.code == "deadline_exhausted" for item in scan.diagnostics))

    def test_mining_is_filesystem_neutral(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        before = {
            str(path.relative_to(self.base)): path.read_bytes()
            for path in self.base.rglob("*") if path.is_file()
        }
        report, exit_code = session_learning.mine_history(
            self.root, home_dir=self.home
        )
        after = {
            str(path.relative_to(self.base)): path.read_bytes()
            for path in self.base.rglob("*") if path.is_file()
        }
        self.assertEqual(0, exit_code)
        self.assertEqual("complete", report["status"])
        self.assertEqual(before, after)

    def test_evidence_changes_invalidate_continuation(self) -> None:
        self.write_session("session-1", self.root, self.normalized_records("session-1"))
        first, _ = session_learning.mine_history(self.root, home_dir=self.home)
        evidence_dir = self.root / ".agents" / "learning" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "new.json").write_text(
            json.dumps({"id": "evidence.changed", "authority": "project"}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "scan fingerprint changed"):
            session_learning.mine_history(
                self.root, home_dir=self.home,
                expect_scan=first["scan_fingerprint"],
            )


class EvidencePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.root = base / "project"
        self.root.mkdir()
        self.home = base / "home"
        sessions = self.home / ".codex" / "sessions"
        sessions.mkdir(parents=True)
        values = recovery_events()
        records: list[dict[str, object]] = [{
            "type": "session_meta",
            "payload": {
                "id": "session-1", "cwd": str(self.root),
                "timestamp": "2026-09-09T00:00:00Z",
            },
        }]
        for value in values:
            records.append({
                "kind": value.kind, "session_id": value.session_id,
                "event_id": value.event_id, "ordinal": value.ordinal,
                "operation": value.operation, "strategy": value.strategy,
                "targets": list(value.targets), "resources": list(value.resources),
                "input": {"identity": value.input_fingerprint},
                "outcome": value.outcome, "failure_class": value.failure_class,
                "diagnostic_code": value.diagnostic_code,
            })
        (sessions / "session.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in records), encoding="utf-8"
        )
        self.candidate = history.mine_recoveries(values).candidates[0]
        candidate = self.candidate
        self.evidence = {
            "schema_version": 2, "record_type": "evidence",
            "id": f"evidence.recovery.{candidate.source_fingerprint[:20]}",
            "authority": "project", "session_id": candidate.session_id,
            "signal": "recovery_pair", "situation": "A bounded operation failed.",
            "attempted_behavior": "The initial strategy failed.",
            "feedback": candidate.contrast,
            "corrected_behavior": "A changed strategy was verified.",
            "outcome": "The corresponding verification succeeded.",
            "created_at": "2026-09-09T00:00:00Z",
            "behavior_delta": candidate.behavior_delta,
            "source": {
                "host": "codex", "failure_event_id": candidate.failure_id,
                "repair_event_ids": list(candidate.repair_ids),
                "verification_event_id": candidate.verification_id,
                "supporting_event_ids": list(candidate.supporting_ids),
                "source_fingerprint": candidate.source_fingerprint,
                "content_fingerprint": candidate.content_fingerprint,
                "analyzer_version": candidate.analyzer_version,
            },
        }
        evidence_dir = self.root / ".agents" / "learning" / "evidence"
        evidence_dir.mkdir(parents=True)
        self.path = evidence_dir / f"{self.evidence['id']}.json"
        self.path.write_text(json.dumps(self.evidence, indent=2) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def manifest(self, repair_ids: list[str]) -> dict[str, object]:
        return {
            "manifest_schema_version": 2, "origin": "historical_mining",
            "changes": [{
                "path": f".agents/learning/evidence/{self.path.name}",
                "evidence_patch": {
                    "expected_sha256": session_learning.canonical_record_sha256(self.evidence),
                    "replace_interpretation": {
                        "contrast": self.candidate.contrast + " verified",
                        "causal_roles": {
                            "failure_event_id": self.candidate.failure_id,
                            "repair_event_ids": repair_ids,
                            "verification_event_id": self.candidate.verification_id,
                            "supporting_event_ids": list(self.candidate.supporting_ids),
                        },
                        "behavior_delta": self.candidate.behavior_delta,
                        "analyzer_version": "2",
                    },
                },
            }],
        }

    def test_reinterpretation_rescans_source_and_recomputes_content_hash(self) -> None:
        result = session_learning.apply_manifest(
            self.root, self.manifest(list(self.candidate.repair_ids)), home_dir=self.home
        )
        updated = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertTrue(result["changed"])
        self.assertNotEqual(
            self.evidence["source"]["content_fingerprint"],
            updated["source"]["content_fingerprint"],
        )
        self.assertEqual("2", updated["source"]["analyzer_version"])

    def test_reinterpretation_rejects_unverifiable_event_reference(self) -> None:
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "missing or duplicate"):
            session_learning.apply_manifest(
                self.root, self.manifest(["missing-repair"]), home_dir=self.home
            )
        self.assertEqual(before, self.path.read_bytes())

    def test_new_recovery_evidence_recomputes_caller_fingerprints(self) -> None:
        self.path.unlink()
        proposed = json.loads(json.dumps(self.evidence))
        proposed["source"]["source_fingerprint"] = "0" * 64
        proposed["source"]["content_fingerprint"] = "0" * 64
        session_learning.apply_manifest(
            self.root,
            {"manifest_schema_version": 2, "origin": "historical_mining", "changes": [{
                "path": f".agents/learning/evidence/{self.path.name}", "json": proposed
            }]},
            home_dir=self.home,
        )
        written = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(
            self.evidence["source"]["source_fingerprint"],
            written["source"]["source_fingerprint"],
        )
        self.assertEqual(
            self.evidence["source"]["content_fingerprint"],
            written["source"]["content_fingerprint"],
        )


if __name__ == "__main__":
    unittest.main()
