#!/usr/bin/env python3
"""Normalize bounded history records and mine conservative recovery evidence.

The analyzer intentionally keeps normalized events in memory.  It emits compact
recovery candidates, never raw history or operation input.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterable, Iterator, Mapping, Protocol, Sequence


ANALYZER_VERSION = "1.0"
HISTORY_HOST = "codex"
MAX_PROXIMITY = 12
MAX_CONTRAST_CHARS = 500
MAX_CANDIDATE_BYTES = 2500
MAX_EVENT_BYTES = 2000
MAX_ID_CHARS = 120
MAX_INPUT_DEPTH = 3
MAX_INPUT_ITEMS = 12
MAX_DISCOVERY_ENTRIES = 10_000
MAX_METADATA_BYTES = 4 * 1024
MAX_RECORD_BYTES = 1024 * 1024
MAX_SESSION_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_SESSIONS = 50
MAX_EVENTS = 20_000
MAX_CANDIDATES = 100
MAX_DIAGNOSTICS = 100
MAX_REPORT_BYTES = 256 * 1024
MAX_COMPACT_REPORT_BYTES = 16 * 1024
PAGE_SIZE = 20
DIAGNOSTIC_PAGE_SIZE = 20
SCAN_DEADLINE_SECONDS = 30.0

EVENT_KINDS = {"operation", "user_boundary"}
OUTCOMES = {"success", "failure", "unknown"}
INERT_KINDS = {"heartbeat", "progress", "usage", "telemetry"}
OPERATIONS = {
    "call_tool",
    "edit_file",
    "fetch",
    "install_dependency",
    "read_file",
    "read_resource",
    "request_permission",
    "retry",
    "run_command",
    "search",
    "test",
    "verify",
    "workflow_step",
    "write_file",
}
STRATEGIES = {
    "alternate_tool",
    "backoff",
    "broadened_scope",
    "changed_arguments",
    "changed_retry_strategy",
    "chunked_resource",
    "correct_tool_convention",
    "corrected_command",
    "corrected_path",
    "dependency_install",
    "direct",
    "escalated_permission",
    "full",
    "narrowed_scope",
    "paginated_resource",
    "reordered_workflow",
    "retry_same",
    "source_first",
    "streamed_resource",
    "targeted",
    "verify_after",
}
CORRECTION_STRATEGIES = {
    "alternate_tool",
    "backoff",
    "broadened_scope",
    "changed_arguments",
    "changed_retry_strategy",
    "chunked_resource",
    "correct_tool_convention",
    "corrected_command",
    "corrected_path",
    "escalated_permission",
    "narrowed_scope",
    "paginated_resource",
    "reordered_workflow",
    "source_first",
    "streamed_resource",
    "verify_after",
}
FAILURE_CLASSES = {
    "dependency",
    "invocation",
    "permission",
    "resource_limit",
    "runtime",
    "test",
    "timeout",
}
DIAGNOSTIC_MESSAGES = {
    "command_failed": "command failed",
    "dependency_missing": "dependency missing",
    "file_not_found": "file not found",
    "invalid_argument": "invalid argument",
    "permission_denied": "permission denied",
    "resource_too_large": "resource too large",
    "search_no_results": "search returned no results",
    "test_failed": "test failed",
    "timeout": "operation timed out",
    "tool_error": "tool error",
}

_OPERATION_FAMILIES = {
    "call_tool": "tool",
    "edit_file": "file",
    "fetch": "resource",
    "install_dependency": "dependency",
    "read_file": "file",
    "read_resource": "resource",
    "request_permission": "permission",
    "retry": "command",
    "run_command": "command",
    "search": "search",
    "test": "verification",
    "verify": "verification",
    "workflow_step": "workflow",
    "write_file": "file",
}
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^/@\s:]+(?::[^/@\s]*)?@")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]\s*[^\s,;]+"
)
_SECRET_PREFIX = re.compile(
    r"\b(?:gh[pousr]_|sk-[A-Za-z0-9_-]*|xox[baprs]-)[A-Za-z0-9_-]{12,}\b"
)
_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:[/\\](?:[^\s;,]+)")
_HOME_PATH = re.compile(r"(?i)(?:/home/|/users/)[^/\s]+(?:/[^\s;,]+)?")
_POSIX_PATH = re.compile(r"(?<![:/\w>])/(?!/)[^\s,;]+")
_HIGH_ENTROPY = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,119}$")
_SAFE_INPUT_KEYS = {
    "args",
    "chunk_size",
    "command",
    "method",
    "mode",
    "operation",
    "options",
    "path",
    "paths",
    "pattern",
    "permission",
    "query",
    "resource",
    "retry",
    "scope",
    "strategy",
    "tool",
    "url",
    "workflow",
}
_SECRET_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
}


class HistoryRecordError(ValueError):
    """A history record could not safely participate in causal matching."""

    def __init__(self, message: str, *, event_id: str | None = None) -> None:
        super().__init__(message)
        self.event_id = event_id


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    """An in-memory, bounded representation of one history event."""

    session_id: str
    event_id: str
    timestamp: str | None
    ordinal: int
    kind: str
    operation: str
    strategy: str
    targets: tuple[str, ...]
    resources: tuple[str, ...]
    input_fingerprint: str
    outcome: str
    failure_class: str | None
    diagnostic_code: str | None


@dataclass(frozen=True, slots=True)
class RecoveryCandidate:
    session_id: str
    failure_id: str
    repair_ids: tuple[str, ...]
    verification_id: str
    supporting_ids: tuple[str, ...]
    behavior_delta: dict[str, Any]
    contrast: str
    source_fingerprint: str
    content_fingerprint: str
    authority: str = "project"
    reason_codes: tuple[str, ...] = ("observable_failure", "semantic_change", "verified")
    failure_category: str | None = None
    analyzer_version: str = ANALYZER_VERSION


@dataclass(frozen=True, slots=True)
class RecoveryScanResult:
    candidates: tuple[RecoveryCandidate, ...]
    degraded: bool
    barrier_ids: tuple[str, ...]
    rejection_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanDiagnostic:
    code: str
    message: str
    session_id: str | None = None
    record_id: str | None = None


@dataclass(frozen=True, slots=True)
class SessionMetadata:
    session_id: str
    cwd: Path
    timestamp: str | None
    path: Path
    relative_name: str


@dataclass(slots=True)
class ScanBudget:
    clock: Callable[[], float] = time.monotonic
    deadline_seconds: float = SCAN_DEADLINE_SECONDS
    started_at: float = field(init=False)
    entries: int = 0
    bytes_read: int = 0
    events: int = 0

    def __post_init__(self) -> None:
        self.started_at = self.clock()

    def check_deadline(self) -> None:
        if self.clock() - self.started_at >= self.deadline_seconds:
            raise ScanLimit("deadline_exhausted")

    def add_bytes(self, amount: int, *, limit: int = MAX_TOTAL_BYTES) -> None:
        if amount < 0 or self.bytes_read + amount > limit:
            raise ScanLimit("total_input_exhausted")
        self.bytes_read += amount


class ScanLimit(RuntimeError):
    pass


class SessionScanner(Protocol):
    def scan(
        self,
        root: str | os.PathLike[str],
        *,
        home_dir: str | os.PathLike[str] | None = None,
        since: str | None = None,
        session_id: str | None = None,
        budget: ScanBudget | None = None,
    ) -> "HistoryScan": ...


@dataclass(frozen=True, slots=True)
class HistoryScan:
    status: str
    candidates: tuple[RecoveryCandidate, ...]
    diagnostics: tuple[ScanDiagnostic, ...]
    selected_sessions: int
    scanned_sessions: int
    skipped_sessions: int
    failed_sessions: int
    discovery_complete: bool
    scan_fingerprint: str
    rejection_counts: Mapping[str, int]


def _identifier(value: Any) -> str:
    return "_".join(str(value).strip().lower().replace("-", "_").split())


def _bounded_text(value: Any, *, maximum: int = 240) -> str:
    text = _CONTROL_CHARS.sub(" ", str(value))
    return " ".join(text.split())[:maximum]


def _replace_prefix(
    value: str,
    prefix: str | None,
    replacement: str,
    *,
    case_sensitive: bool,
) -> str:
    if not prefix:
        return value
    normalized_prefix = str(prefix).replace("\\", "/").rstrip("/")
    compared_value = value if case_sensitive else value.lower()
    compared_prefix = normalized_prefix if case_sensitive else normalized_prefix.lower()
    if compared_value == compared_prefix:
        return replacement
    if compared_value.startswith(compared_prefix + "/"):
        return replacement + value[len(normalized_prefix) :]
    return value


def _normalized_locator(
    value: Any, *, project_root: str | None = None, home_dir: str | None = None
) -> str:
    raw = _bounded_text(value)
    windows_semantics = bool(re.match(r"(?i)^[a-z]:[/\\]", raw) or "\\" in raw)
    result = raw.replace("\\", "/").rstrip("/")
    if windows_semantics:
        result = result.lower()
    result = _replace_prefix(
        result, project_root, "<project>", case_sensitive=not windows_semantics
    )
    result = _replace_prefix(result, home_dir, "<home>", case_sensitive=not windows_semantics)
    return _redact(result)


def _redact(value: str) -> str:
    result = _CONTROL_CHARS.sub(" ", value)
    result = _URL_CREDENTIALS.sub(r"\1<credentials>@", result)
    result = _EMAIL.sub("<email>", result)
    result = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", result)
    result = _SECRET_PREFIX.sub("<redacted>", result)
    result = _WINDOWS_PATH.sub("<path>", result)
    result = _HOME_PATH.sub("<home-path>", result)
    result = _POSIX_PATH.sub("<path>", result)

    def redact_entropy(match: re.Match[str]) -> str:
        token = match.group(0)
        categories = sum(
            bool(re.search(pattern, token))
            for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[_+/=-]")
        )
        return "<redacted>" if categories >= 3 else token

    return " ".join(_HIGH_ENTROPY.sub(redact_entropy, result).split())


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalized_input(value: Any, *, depth: int = 0, field: str = "") -> Any:
    """Return a small allowlisted input shape suitable for fingerprinting."""
    if field in _SECRET_KEYS:
        return "<redacted>"
    if depth > MAX_INPUT_DEPTH:
        return "<truncated>"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key in sorted(value, key=lambda item: str(item))[:MAX_INPUT_ITEMS]:
            key = _identifier(raw_key)
            if key not in _SAFE_INPUT_KEYS and key not in _SECRET_KEYS:
                continue
            result[key] = _normalized_input(value[raw_key], depth=depth + 1, field=key)
        return result
    if isinstance(value, (list, tuple)):
        return [
            _normalized_input(item, depth=depth + 1, field=field)
            for item in value[:MAX_INPUT_ITEMS]
        ]
    if isinstance(value, str):
        return _redact(_bounded_text(value))
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return "<unsupported>"


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and _SAFE_ID.fullmatch(value) is not None


def _event_projection(event: NormalizedEvent) -> dict[str, Any]:
    return {
        "session_id": event.session_id,
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "ordinal": event.ordinal,
        "kind": event.kind,
        "operation": event.operation,
        "strategy": event.strategy,
        "targets": event.targets,
        "resources": event.resources,
        "input_fingerprint": event.input_fingerprint,
        "outcome": event.outcome,
        "failure_class": event.failure_class,
        "diagnostic_code": event.diagnostic_code,
    }


def _validate_normalized_event(event: NormalizedEvent) -> list[str]:
    errors: list[str] = []
    if not _valid_id(event.session_id) or not _valid_id(event.event_id):
        errors.append("normalized event IDs must be bounded and free of control characters")
    if event.timestamp is not None and (
        not isinstance(event.timestamp, str)
        or len(event.timestamp) > 80
        or event.timestamp != _bounded_text(event.timestamp, maximum=80)
    ):
        errors.append("normalized event timestamp is invalid")
    if not isinstance(event.ordinal, int) or isinstance(event.ordinal, bool) or event.ordinal < 0:
        errors.append("normalized event ordinal is invalid")
    if event.kind not in EVENT_KINDS:
        errors.append("normalized event kind is unsupported")
    if event.kind == "operation" and (
        event.operation not in OPERATIONS
        or event.strategy not in STRATEGIES
        or event.outcome not in OUTCOMES
    ):
        errors.append("normalized operation structure is unsupported")
    if event.kind == "user_boundary" and any(
        (
            event.operation,
            event.strategy,
            event.targets,
            event.resources,
            event.input_fingerprint,
            event.failure_class,
            event.diagnostic_code,
        )
    ):
        errors.append("user boundary contains consequential operation fields")
    if event.failure_class is not None and event.failure_class not in FAILURE_CLASSES | {
        "probe",
        "expected",
    }:
        errors.append("normalized failure class is unsupported")
    if event.diagnostic_code is not None and event.diagnostic_code not in DIAGNOSTIC_MESSAGES:
        errors.append("normalized diagnostic code is unsupported")
    if event.kind == "operation" and not re.fullmatch(r"[0-9a-f]{64}", event.input_fingerprint):
        errors.append("normalized input fingerprint must be SHA-256 hex")
    for name, locators in (("targets", event.targets), ("resources", event.resources)):
        if not isinstance(locators, tuple) or len(locators) > 8:
            errors.append(f"normalized event {name} are invalid")
            continue
        if any(
            not isinstance(item, str)
            or not item
            or len(item) > 240
            or item != _normalized_locator(item)
            for item in locators
        ):
            errors.append(f"normalized event {name} are not safely normalized")
    try:
        size = len(
            json.dumps(_event_projection(event), separators=(",", ":"), ensure_ascii=True).encode(
                "utf-8"
            )
        )
    except (TypeError, ValueError):
        errors.append("normalized event cannot be represented safely")
    else:
        if size > MAX_EVENT_BYTES:
            errors.append(f"normalized event exceeds {MAX_EVENT_BYTES} bytes")
    return errors


def normalize_event(
    record: Mapping[str, Any],
    *,
    project_root: str | None = None,
    home_dir: str | None = None,
) -> NormalizedEvent:
    """Normalize one allowlisted record or raise a causal-barrier error."""
    if not isinstance(record, Mapping):
        raise HistoryRecordError("history record must be an object")
    event_id_value = record.get("event_id")
    event_id = event_id_value if _valid_id(event_id_value) else None
    if record.get("truncated") is True:
        raise HistoryRecordError("truncated history record", event_id=event_id)
    kind = _identifier(record.get("kind", ""))
    if kind not in EVENT_KINDS:
        raise HistoryRecordError("unsupported consequential history record", event_id=event_id)
    session_id_value = record.get("session_id")
    session_id = session_id_value if _valid_id(session_id_value) else None
    if session_id is None or event_id is None:
        raise HistoryRecordError("history record lacks stable identity", event_id=event_id)
    ordinal = record.get("ordinal")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        raise HistoryRecordError("history record lacks a valid ordinal", event_id=event_id)
    timestamp_value = record.get("timestamp")
    timestamp = (
        _bounded_text(timestamp_value, maximum=80) if timestamp_value is not None else None
    )
    if kind == "user_boundary":
        boundary = NormalizedEvent(
            session_id,
            event_id,
            timestamp,
            ordinal,
            kind,
            "",
            "",
            (),
            (),
            "",
            "unknown",
            None,
            None,
        )
        if _validate_normalized_event(boundary):
            raise HistoryRecordError("invalid user boundary", event_id=event_id)
        return boundary

    operation = _identifier(record.get("operation", ""))
    strategy = _identifier(record.get("strategy", ""))
    outcome = _identifier(record.get("outcome", "unknown"))
    failure_class_value = record.get("failure_class")
    failure_class = _identifier(failure_class_value) if failure_class_value is not None else None
    diagnostic_value = record.get("diagnostic_code")
    diagnostic_code = _identifier(diagnostic_value) if diagnostic_value is not None else None
    if operation not in OPERATIONS or strategy not in STRATEGIES or outcome not in OUTCOMES:
        raise HistoryRecordError("unsupported normalized operation structure", event_id=event_id)
    if failure_class is not None and failure_class not in FAILURE_CLASSES | {"probe", "expected"}:
        raise HistoryRecordError("unsupported failure class", event_id=event_id)
    if diagnostic_code is not None and diagnostic_code not in DIAGNOSTIC_MESSAGES:
        raise HistoryRecordError("unsupported diagnostic code", event_id=event_id)
    for locator_field in ("targets", "resources"):
        value = record.get(locator_field, [])
        if (
            not isinstance(value, (list, tuple))
            or len(value) > 8
            or any(not isinstance(item, str) or not item or len(item) > 240 for item in value)
        ):
            raise HistoryRecordError(f"invalid {locator_field}", event_id=event_id)
    targets = tuple(
        item
        for item in (
            _normalized_locator(value, project_root=project_root, home_dir=home_dir)
            for value in record.get("targets", [])
        )
        if item
    )
    resources = tuple(
        item
        for item in (
            _normalized_locator(value, project_root=project_root, home_dir=home_dir)
            for value in record.get("resources", [])
        )
        if item
    )
    compact_input = _normalized_input(record.get("input", {}))
    input_fingerprint = _fingerprint(
        {
            "operation": operation,
            "strategy": strategy,
            "targets": targets,
            "resources": resources,
            "input": compact_input,
        }
    )
    normalized = NormalizedEvent(
        session_id,
        event_id,
        timestamp,
        ordinal,
        kind,
        operation,
        strategy,
        targets,
        resources,
        input_fingerprint,
        outcome,
        failure_class,
        diagnostic_code,
    )
    if _validate_normalized_event(normalized):
        raise HistoryRecordError("normalized event exceeds safe bounds", event_id=event_id)
    return normalized


def _identity(event: NormalizedEvent) -> set[str]:
    return set(event.targets) | set(event.resources)


def _overlaps(first: NormalizedEvent, second: NormalizedEvent) -> bool:
    return bool(set(first.targets) & set(second.targets)) or bool(
        set(first.resources) & set(second.resources)
    )


def _family(event: NormalizedEvent) -> str:
    return _OPERATION_FAMILIES.get(event.operation, "")


def _observable_failure(event: NormalizedEvent) -> bool:
    return (
        event.kind == "operation"
        and event.outcome == "failure"
        and event.failure_class in FAILURE_CLASSES
        and event.diagnostic_code in DIAGNOSTIC_MESSAGES
        and bool(_identity(event))
    )


def _is_repair(failure: NormalizedEvent, candidate: NormalizedEvent) -> bool:
    return (
        candidate.kind == "operation"
        and candidate.session_id == failure.session_id
        and candidate.operation == failure.operation
        and _overlaps(failure, candidate)
        and candidate.strategy in CORRECTION_STRATEGIES
        and candidate.strategy != failure.strategy
        and candidate.input_fingerprint != failure.input_fingerprint
        and candidate.outcome == "success"
    )


def _is_verification(
    failure: NormalizedEvent,
    repairs: Sequence[NormalizedEvent],
    candidate: NormalizedEvent,
) -> bool:
    if candidate.kind != "operation" or candidate.outcome != "success":
        return False
    if candidate.session_id != failure.session_id or not _overlaps(failure, candidate):
        return False
    if candidate.input_fingerprint == failure.input_fingerprint:
        return False
    return candidate.operation == failure.operation and bool(repairs)


def _step(event: NormalizedEvent) -> dict[str, str]:
    return {"operation": event.operation, "strategy": event.strategy}


def _behavior_delta(
    failure: NormalizedEvent, repairs: Sequence[NormalizedEvent]
) -> dict[str, Any] | None:
    if not repairs:
        return None
    value: dict[str, Any] = {
        "type": "replace",
        "before": [_step(failure)],
        "after": [_step(item) for item in repairs[-3:]],
    }
    return value if not validate_behavior_delta(value) else None


def validate_behavior_delta(value: Any) -> list[str]:
    """Validate the compact allowlisted before/after behavior representation."""
    if not isinstance(value, Mapping):
        return ["behavior_delta must be an object"]
    errors: list[str] = []
    if set(value) != {"type", "before", "after"}:
        errors.append("behavior_delta must contain only type, before, and after")
    delta_type = value.get("type")
    if delta_type not in {"add", "remove", "replace", "reorder"}:
        errors.append("behavior_delta.type must be add, remove, replace, or reorder")
    steps_by_side: dict[str, list[tuple[str, str]]] = {}
    for side in ("before", "after"):
        steps = value.get(side)
        if not isinstance(steps, list) or len(steps) > 3:
            errors.append(f"behavior_delta.{side} must contain at most three ordered steps")
            continue
        normalized_steps: list[tuple[str, str]] = []
        for step in steps:
            if not isinstance(step, Mapping) or set(step) != {"operation", "strategy"}:
                errors.append(f"behavior_delta.{side} steps require operation and strategy")
                continue
            operation = step.get("operation")
            strategy = step.get("strategy")
            if operation not in OPERATIONS or strategy not in STRATEGIES:
                errors.append(f"behavior_delta.{side} contains an unsupported step")
                continue
            normalized_steps.append((str(operation), str(strategy)))
        steps_by_side[side] = normalized_steps
    if errors:
        return errors
    before = steps_by_side["before"]
    after = steps_by_side["after"]
    if delta_type == "add" and (before or not after):
        errors.append("behavior_delta add requires empty before and non-empty after")
    elif delta_type == "remove" and (not before or after):
        errors.append("behavior_delta remove requires non-empty before and empty after")
    elif delta_type == "replace" and (not before or not after or before == after):
        errors.append("behavior_delta replace requires distinct non-empty sides")
    elif delta_type == "reorder" and (
        len(before) < 2 or Counter(before) != Counter(after) or before == after
    ):
        errors.append("behavior_delta reorder requires the same steps in a different order")
    return errors


def build_compact_contrast(
    failure: NormalizedEvent, repairs: Sequence[NormalizedEvent]
) -> str:
    """Render a bounded contrast exclusively from normalized allowlisted fields."""
    if not repairs:
        return ""
    before = f"{failure.operation}/{failure.strategy}"
    after = ", ".join(f"{item.operation}/{item.strategy}" for item in repairs[-3:])
    diagnostic = DIAGNOSTIC_MESSAGES.get(failure.diagnostic_code or "", "")
    targets = sorted(_identity(failure))[:3]
    target_text = f"; target {', '.join(targets)}" if targets else ""
    diagnostic_text = f"; {diagnostic}" if diagnostic else ""
    return _redact(f"{before} -> {after}{target_text}{diagnostic_text}")[:MAX_CONTRAST_CHARS]


def _infer_authority(
    failure: NormalizedEvent, repairs: Sequence[NormalizedEvent]
) -> str:
    """Infer the storage authority without retaining user or transcript prose."""
    local_strategies = {"correct_tool_convention", "escalated_permission", "backoff"}
    if failure.operation in {"request_permission", "call_tool"} and any(
        item.strategy in local_strategies for item in repairs
    ):
        return "local"
    return "project"


def _candidate_payload(candidate: RecoveryCandidate) -> dict[str, Any]:
    return {
        "session_id": candidate.session_id,
        "failure_id": candidate.failure_id,
        "repair_ids": list(candidate.repair_ids),
        "verification_id": candidate.verification_id,
        "supporting_ids": list(candidate.supporting_ids),
        "behavior_delta": candidate.behavior_delta,
        "contrast": candidate.contrast,
        "source_fingerprint": candidate.source_fingerprint,
        "content_fingerprint": candidate.content_fingerprint,
        "authority": candidate.authority,
        "reason_codes": list(candidate.reason_codes),
        "failure_category": candidate.failure_category,
        "analyzer_version": candidate.analyzer_version,
    }


def _make_candidate(
    failure: NormalizedEvent,
    repairs: Sequence[NormalizedEvent],
    verification: NormalizedEvent,
    supporting: Sequence[NormalizedEvent],
) -> RecoveryCandidate | None:
    ordered_repairs = tuple(sorted(repairs[-3:], key=lambda item: item.ordinal))
    ordered_support = tuple(sorted(supporting[-4:], key=lambda item: item.ordinal))
    delta = _behavior_delta(failure, ordered_repairs)
    if delta is None:
        return None
    contrast = build_compact_contrast(failure, ordered_repairs)
    if not contrast:
        return None
    source_fingerprint = _fingerprint(
        [HISTORY_HOST, failure.session_id, failure.event_id, verification.event_id]
    )
    causal_roles = {
        "failure_event_id": failure.event_id,
        "repair_event_ids": [item.event_id for item in ordered_repairs],
        "verification_event_id": verification.event_id,
        "supporting_event_ids": [item.event_id for item in ordered_support],
    }
    content_fingerprint = _fingerprint(
        {"contrast": contrast, "causal_roles": causal_roles, "behavior_delta": delta}
    )
    candidate = RecoveryCandidate(
        session_id=failure.session_id,
        failure_id=failure.event_id,
        repair_ids=tuple(item.event_id for item in ordered_repairs),
        verification_id=verification.event_id,
        supporting_ids=tuple(item.event_id for item in ordered_support),
        behavior_delta=delta,
        contrast=contrast,
        source_fingerprint=source_fingerprint,
        content_fingerprint=content_fingerprint,
        authority=_infer_authority(failure, ordered_repairs),
        failure_category=failure.failure_class,
    )
    events = {item.event_id: item for item in (failure, *ordered_repairs, verification, *ordered_support)}
    if validate_recovery_candidate(candidate, events):
        return None
    serialized = json.dumps(_candidate_payload(candidate), separators=(",", ":"), ensure_ascii=True)
    return candidate if len(serialized.encode("utf-8")) <= MAX_CANDIDATE_BYTES else None


def validate_recovery_candidate(
    candidate: RecoveryCandidate, events: Mapping[str, NormalizedEvent]
) -> list[str]:
    """Validate causal-slice cardinality, identity, ordering, and compactness."""
    errors: list[str] = []
    if not _valid_id(candidate.session_id):
        errors.append(f"candidate session_id must contain at most {MAX_ID_CHARS} characters")
    repair_ids = candidate.repair_ids if isinstance(candidate.repair_ids, tuple) else ()
    supporting_ids = (
        candidate.supporting_ids if isinstance(candidate.supporting_ids, tuple) else ()
    )
    candidate_ids: list[Any] = [
        candidate.failure_id,
        *repair_ids,
        candidate.verification_id,
        *supporting_ids,
    ]
    if any(not _valid_id(item) for item in candidate_ids):
        errors.append(f"candidate event IDs must contain at most {MAX_ID_CHARS} characters")
        return errors
    if not candidate.failure_id or not candidate.verification_id:
        errors.append("candidate requires exactly one failure and one verification")
    if not 1 <= len(repair_ids) <= 3:
        errors.append("candidate requires one to three repair IDs")
    if len(supporting_ids) > 4:
        errors.append("candidate allows at most four supporting IDs")
    roles = [
        candidate.failure_id,
        *repair_ids,
        candidate.verification_id,
        *supporting_ids,
    ]
    if len(roles) != len(set(roles)):
        errors.append("candidate event roles must be unique")
    resolved = [events.get(event_id) for event_id in roles]
    if any(item is None for item in resolved):
        errors.append("candidate references an unknown event")
        return errors
    typed = [item for item in resolved if item is not None]
    if any(item.session_id != candidate.session_id for item in typed):
        errors.append("candidate events must share the same session")
    failure = events[candidate.failure_id]
    verification = events[candidate.verification_id]
    repairs = [events[event_id] for event_id in repair_ids]
    support = [events[event_id] for event_id in supporting_ids]
    if any(_validate_normalized_event(item) for item in typed):
        errors.append("candidate semantic events must be safely normalized")
    if repairs != sorted(repairs, key=lambda item: item.ordinal):
        errors.append("candidate repairs must be ordinal-sorted")
    if support != sorted(support, key=lambda item: item.ordinal):
        errors.append("candidate supporting events must be ordinal-sorted")
    if not all(failure.ordinal < item.ordinal < verification.ordinal for item in repairs):
        errors.append("candidate must be ordered failure, repairs, verification")
    if not all(failure.ordinal < item.ordinal < verification.ordinal for item in support):
        errors.append("candidate support must be strictly between endpoints")
    errors.extend(validate_behavior_delta(candidate.behavior_delta))
    if not _observable_failure(failure):
        errors.append("candidate semantic failure must be observable")
    if any(not _is_repair(failure, repair) for repair in repairs):
        errors.append("candidate semantic repairs must be valid corrections")
    if not _is_verification(failure, repairs, verification):
        errors.append("candidate semantic verification must be a later success")
    if not isinstance(candidate.contrast, str) or not candidate.contrast or len(candidate.contrast) > 500:
        errors.append("candidate contrast must contain at most 500 characters")
    elif candidate.contrast != _redact(candidate.contrast):
        errors.append("candidate contrast must be normalized and redacted")
    for fingerprint in (candidate.source_fingerprint, candidate.content_fingerprint):
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            errors.append("candidate fingerprints must be SHA-256 hex")
    if candidate.authority not in {"project", "local"}:
        errors.append("candidate authority must be project or local")
    if (
        not isinstance(candidate.reason_codes, tuple)
        or not candidate.reason_codes
        or any(not _valid_id(item) for item in candidate.reason_codes)
    ):
        errors.append("candidate reason codes must be bounded identifiers")
    if not errors:
        try:
            size = len(
                json.dumps(
                    _candidate_payload(candidate), separators=(",", ":"), ensure_ascii=True
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            errors.append("candidate cannot be represented safely")
        else:
            if size > MAX_CANDIDATE_BYTES:
                errors.append(f"candidate exceeds {MAX_CANDIDATE_BYTES} bytes")
    return errors


@dataclass(slots=True)
class _PendingRecovery:
    failure: NormalizedEvent
    repairs: list[NormalizedEvent]
    supporting: list[NormalizedEvent]


def mine_recoveries(
    records: Iterable[NormalizedEvent | Mapping[str, Any]],
    *,
    project_root: str | None = None,
    home_dir: str | None = None,
) -> RecoveryScanResult:
    """Mine high-confidence recovery candidates from a bounded event stream."""
    candidates: list[RecoveryCandidate] = []
    barriers: list[str] = []
    rejections: Counter[str] = Counter()
    pending: _PendingRecovery | None = None
    degraded = False

    for index, record in enumerate(records):
        if (
            isinstance(record, Mapping)
            and _identifier(record.get("kind", "")) in INERT_KINDS
            and set(record)
            <= {"kind", "event_id", "session_id", "ordinal", "timestamp"}
        ):
            continue
        try:
            normalized = (
                record
                if isinstance(record, NormalizedEvent)
                else normalize_event(record, project_root=project_root, home_dir=home_dir)
            )
            if _validate_normalized_event(normalized):
                raise HistoryRecordError(
                    "unsupported normalized event", event_id=normalized.event_id
                )
        except (HistoryRecordError, TypeError, ValueError) as exc:
            degraded = True
            event_id = getattr(exc, "event_id", None)
            if event_id is None and isinstance(record, Mapping):
                event_id = record.get("event_id")
            barriers.append(_bounded_text(event_id or f"record-{index}", maximum=120))
            pending = None
            continue

        if normalized.kind == "user_boundary":
            if pending is not None:
                rejections["user_boundary"] += 1
            pending = None
            continue
        if pending is not None and normalized.session_id != pending.failure.session_id:
            pending = None
        if normalized.operation == "install_dependency" or normalized.strategy == "dependency_install":
            if pending is not None:
                rejections["stronger_intervening_explanation"] += 1
            pending = None
            continue
        if pending is not None and normalized.ordinal - pending.failure.ordinal > MAX_PROXIMITY:
            rejections["proximity_exceeded"] += 1
            pending = None

        if pending is not None:
            if _is_repair(pending.failure, normalized):
                if len(pending.repairs) == 3:
                    rejections["repair_limit"] += 1
                    pending = None
                else:
                    pending.repairs.append(normalized)
                continue
            if _is_verification(pending.failure, pending.repairs, normalized):
                candidate = _make_candidate(
                    pending.failure, pending.repairs, normalized, pending.supporting
                )
                if candidate is not None:
                    candidates.append(candidate)
                pending = None
                continue
            if (
                pending.repairs
                and normalized.outcome != "failure"
                and _overlaps(pending.failure, normalized)
                and len(pending.supporting) < 4
            ):
                pending.supporting.append(normalized)

        if _observable_failure(normalized):
            pending = _PendingRecovery(normalized, [], [])

    return RecoveryScanResult(tuple(candidates), degraded, tuple(barriers), dict(rejections))


def _normalized_path_key(path: Path) -> str:
    value = str(path.expanduser().resolve()).replace("\\", "/").rstrip("/")
    return value.casefold() if os.name == "nt" else value


def _cwd_matches(root: Path, cwd: Path) -> bool:
    root_key = _normalized_path_key(root)
    cwd_key = _normalized_path_key(cwd)
    return cwd_key == root_key or cwd_key.startswith(root_key + "/")


def _parse_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid ISO date: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bounded_json_lines(path: Path, budget: ScanBudget) -> Iterator[tuple[int, Mapping[str, Any]]]:
    session_bytes = 0
    with path.open("rb") as stream:
        ordinal = 0
        while True:
            budget.check_deadline()
            line = stream.readline(MAX_RECORD_BYTES + 1)
            if not line:
                break
            ordinal += 1
            if len(line) > MAX_RECORD_BYTES:
                raise ScanLimit("record_size_exhausted")
            if session_bytes + len(line) > MAX_SESSION_BYTES:
                raise ScanLimit("session_size_exhausted")
            budget.add_bytes(len(line))
            session_bytes += len(line)
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                yield ordinal, {"_barrier": "malformed_record", "_error": type(exc).__name__}
                continue
            if not isinstance(value, Mapping):
                yield ordinal, {"_barrier": "non_object_record"}
                continue
            yield ordinal, value


def _metadata_from_prefix(path: Path, root_dir: Path, budget: ScanBudget) -> SessionMetadata | None:
    budget.check_deadline()
    with path.open("rb") as stream:
        prefix = stream.read(MAX_METADATA_BYTES + 1)
    budget.add_bytes(len(prefix))
    if len(prefix) > MAX_METADATA_BYTES:
        prefix = prefix[:MAX_METADATA_BYTES]
    for line in prefix.splitlines():
        try:
            record = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(record, Mapping):
            continue
        payload = record.get("payload")
        if record.get("type") in {"session_meta", "session_metadata"} and isinstance(
            payload, Mapping
        ):
            session_id = payload.get("id") or payload.get("session_id")
            cwd = payload.get("cwd")
            timestamp = payload.get("timestamp") or record.get("timestamp")
        elif record.get("record_type") in {"session_meta", "session_metadata"}:
            session_id = record.get("id") or record.get("session_id")
            cwd = record.get("cwd")
            timestamp = record.get("timestamp")
        else:
            continue
        if not _valid_id(session_id) or not isinstance(cwd, str) or not cwd:
            return None
        try:
            cwd_path = Path(cwd).expanduser().resolve()
        except OSError:
            return None
        try:
            relative_name = path.relative_to(root_dir).as_posix()
        except ValueError:
            relative_name = path.name
        return SessionMetadata(
            str(session_id), cwd_path, _bounded_text(timestamp, maximum=80) if timestamp else None,
            path, relative_name
        )
    return None


def _discover_jsonl(root: Path, budget: ScanBudget) -> tuple[list[Path], bool]:
    found: list[Path] = []
    complete = True
    stack = [root]
    while stack:
        directory = stack.pop()
        budget.check_deadline()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    budget.entries += 1
                    if budget.entries > MAX_DISCOVERY_ENTRIES:
                        complete = False
                        return found, complete
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False) and entry.name.endswith(".jsonl"):
                        found.append(Path(entry.path))
        except OSError:
            complete = False
    return found, complete


def _ordering_key(item: SessionMetadata) -> tuple[int, str, str]:
    try:
        parsed = _parse_iso(item.timestamp) if item.timestamp else None
    except ValueError:
        parsed = None
    timestamp = int(parsed.timestamp()) if parsed is not None else -1
    return -timestamp, item.session_id, item.relative_name.casefold()


def _stable_event_id(session_id: str, identity: Any) -> str:
    digest = _fingerprint([session_id, str(identity)])[:24]
    return f"event-{digest}"


def _operation_for(tool_name: str, arguments: Mapping[str, Any]) -> str:
    name = _identifier(tool_name)
    if name in {"exec", "exec_command", "shell", "run_command", "write_stdin"}:
        command = str(arguments.get("cmd") or arguments.get("command") or "").casefold()
        if re.search(r"(?:^|\s)(?:npm|pip|uv|cargo|dotnet)\s+(?:install|add)", command):
            return "install_dependency"
        if re.search(r"(?:^|\s)(?:pytest|unittest|npm\s+test|cargo\s+test|dotnet\s+test)", command):
            return "test"
        return "run_command"
    if name in {"apply_patch", "edit", "edit_file", "write_file"}:
        return "edit_file"
    if "search" in name or name in {"find", "rg", "grep"}:
        return "search"
    if name in {"open", "read_file", "view_image", "read_mcp_resource"}:
        return "read_file"
    if "browser" in name or name in {"fetch", "web_run", "web"}:
        return "fetch"
    if "permission" in name or "approval" in name:
        return "request_permission"
    return "call_tool"


def _strategy_for(operation: str, arguments: Mapping[str, Any]) -> str:
    explicit = _identifier(arguments.get("strategy", ""))
    if explicit in STRATEGIES:
        return explicit
    if arguments.get("sandbox_permissions") == "require_escalated":
        return "escalated_permission"
    if operation == "install_dependency":
        return "dependency_install"
    if any(key in arguments for key in ("page", "cursor", "offset", "limit")):
        return "paginated_resource"
    if any(key in arguments for key in ("max_output_tokens", "chunk_size", "max_tokens")):
        return "chunked_resource"
    if any(key in arguments for key in ("path", "paths", "workdir", "cwd")):
        return "targeted"
    return "direct"


def _locators(arguments: Mapping[str, Any], *, keys: Sequence[str]) -> list[str]:
    values: list[str] = []
    for key, value in arguments.items():
        normalized_key = _identifier(key)
        if not any(token in normalized_key for token in keys):
            continue
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            values.extend(str(item) for item in value if isinstance(item, (str, Path)))
    return values[:8]


def _structured_output(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str) and len(value.encode("utf-8", errors="ignore")) <= MAX_RECORD_BYTES:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _outcome_from_output(payload: Mapping[str, Any]) -> tuple[str, str | None, str | None]:
    structured = _structured_output(
        payload.get("output", payload.get("result", payload.get("structuredContent", payload)))
    )
    exit_code = structured.get("exit_code", structured.get("exitCode"))
    is_error = payload.get("is_error", payload.get("isError", structured.get("is_error")))
    status = _identifier(structured.get("status", payload.get("status", "")))
    if isinstance(exit_code, int):
        if exit_code == 0:
            return "success", None, None
        return "failure", "invocation", "command_failed"
    if is_error is True or status in {"error", "failed", "failure"}:
        code = _identifier(structured.get("diagnostic_code", payload.get("diagnostic_code", "tool_error")))
        if code not in DIAGNOSTIC_MESSAGES:
            code = "tool_error"
        failure_class = _identifier(
            structured.get("failure_class", payload.get("failure_class", "runtime"))
        )
        if failure_class not in FAILURE_CLASSES:
            failure_class = "runtime"
        return "failure", failure_class, code
    if status in {"ok", "complete", "completed", "success", "succeeded"} or is_error is False:
        return "success", None, None
    return "unknown", None, None


def _codex_events(
    metadata: SessionMetadata,
    records: Iterable[tuple[int, Mapping[str, Any]]],
    *,
    project_root: Path,
    home_dir: Path,
) -> tuple[list[NormalizedEvent | Mapping[str, Any]], list[ScanDiagnostic]]:
    events: list[NormalizedEvent | Mapping[str, Any]] = []
    diagnostics: list[ScanDiagnostic] = []
    calls: dict[str, tuple[int, str, Mapping[str, Any], str | None]] = {}
    for ordinal, record in records:
        if "_barrier" in record:
            events.append(
                {
                    "kind": "unsupported",
                    "session_id": metadata.session_id,
                    "event_id": _stable_event_id(metadata.session_id, f"barrier:{ordinal}"),
                    "ordinal": ordinal,
                }
            )
            diagnostics.append(
                ScanDiagnostic(str(record["_barrier"]), "causal continuity was lost", metadata.session_id)
            )
            continue
        if record.get("kind") in EVENT_KINDS:
            value = dict(record)
            value.setdefault("session_id", metadata.session_id)
            value.setdefault("event_id", _stable_event_id(metadata.session_id, ordinal))
            value.setdefault("ordinal", ordinal)
            events.append(value)
            continue
        record_type = _identifier(record.get("type", record.get("record_type", "")))
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else record
        payload_type = _identifier(payload.get("type", payload.get("record_type", "")))
        if record_type in {"session_meta", "session_metadata"}:
            continue
        if record_type in INERT_KINDS or payload_type in INERT_KINDS:
            continue
        if payload_type in {"user_message", "user", "input_text"} or (
            record_type in {"event_msg", "message"} and _identifier(payload.get("role", "")) == "user"
        ):
            events.append(
                {
                    "kind": "user_boundary",
                    "session_id": metadata.session_id,
                    "event_id": _stable_event_id(metadata.session_id, payload.get("id", ordinal)),
                    "ordinal": ordinal,
                    "timestamp": record.get("timestamp"),
                }
            )
            continue
        if payload_type in {"function_call", "tool_call", "custom_tool_call"}:
            call_id = str(payload.get("call_id") or payload.get("id") or f"call-{ordinal}")
            name = str(payload.get("name") or payload.get("tool_name") or "")
            raw_arguments = payload.get("arguments", payload.get("input", {}))
            if isinstance(raw_arguments, str):
                try:
                    raw_arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    raw_arguments = {}
            arguments = raw_arguments if isinstance(raw_arguments, Mapping) else {}
            calls[call_id] = (ordinal, name, arguments, record.get("timestamp"))
            continue
        if payload_type in {"function_call_output", "tool_result", "custom_tool_call_output"}:
            call_id = str(payload.get("call_id") or payload.get("tool_call_id") or "")
            call = calls.pop(call_id, None)
            if call is None:
                events.append(
                    {
                        "kind": "unsupported",
                        "session_id": metadata.session_id,
                        "event_id": _stable_event_id(metadata.session_id, f"orphan:{ordinal}"),
                        "ordinal": ordinal,
                    }
                )
                diagnostics.append(
                    ScanDiagnostic("orphan_tool_output", "tool output had no bounded call", metadata.session_id)
                )
                continue
            call_ordinal, name, arguments, timestamp = call
            operation = _operation_for(name, arguments)
            outcome, failure_class, diagnostic_code = _outcome_from_output(payload)
            targets = _locators(arguments, keys=("path", "file", "cwd", "workdir"))
            resources = _locators(arguments, keys=("url", "resource", "query", "pattern"))
            if not targets and not resources:
                resources = [f"tool:{_identifier(name) or 'unknown'}"]
            events.append(
                {
                    "kind": "operation",
                    "session_id": metadata.session_id,
                    "event_id": _stable_event_id(metadata.session_id, call_id),
                    "timestamp": timestamp,
                    "ordinal": call_ordinal,
                    "operation": operation,
                    "strategy": _strategy_for(operation, arguments),
                    "targets": targets,
                    "resources": resources,
                    "input": arguments,
                    "outcome": outcome,
                    "failure_class": failure_class,
                    "diagnostic_code": diagnostic_code,
                }
            )
            continue
        # Assistant prose and reasoning are inert. Unknown tool-like or event records are barriers.
        role = _identifier(payload.get("role", ""))
        if payload_type in {"assistant_message", "reasoning", "output_text"} or role == "assistant":
            continue
        if record_type in {"turn_context", "token_count", "event_msg"} and payload_type in {
            "agent_message", "agent_reasoning", "task_started", "task_complete"
        }:
            continue
        events.append(
            {
                "kind": "unsupported",
                "session_id": metadata.session_id,
                "event_id": _stable_event_id(metadata.session_id, f"unknown:{ordinal}"),
                "ordinal": ordinal,
            }
        )
        diagnostics.append(
            ScanDiagnostic("unsupported_record", "unknown consequential record", metadata.session_id)
        )
    for call_id, (ordinal, _, _, _) in calls.items():
        events.append(
            {
                "kind": "unsupported",
                "session_id": metadata.session_id,
                "event_id": _stable_event_id(metadata.session_id, f"truncated:{call_id}"),
                "ordinal": ordinal,
            }
        )
        diagnostics.append(
            ScanDiagnostic("truncated_tool_call", "tool call lacked an output", metadata.session_id)
        )
    events.sort(
        key=lambda item: item.ordinal if isinstance(item, NormalizedEvent) else int(item.get("ordinal", 0))
    )
    return events, diagnostics


class CodexSessionScanner:
    """Bounded, read-only scanner for Codex JSONL histories."""

    def scan(
        self,
        root: str | os.PathLike[str],
        *,
        home_dir: str | os.PathLike[str] | None = None,
        since: str | None = None,
        session_id: str | None = None,
        budget: ScanBudget | None = None,
    ) -> HistoryScan:
        root_path = Path(root).expanduser().resolve()
        home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
        active_budget = budget or ScanBudget()
        since_dt = _parse_iso(since)
        roots = [home / ".codex" / "sessions", home / ".codex" / "archived_sessions"]
        existing_roots = [path for path in roots if path.is_dir()]
        if not existing_roots:
            return HistoryScan(
                "failed", (), (ScanDiagnostic("history_roots_missing", "Codex history roots are absent"),),
                0, 0, 0, 0, False, _fingerprint([HISTORY_HOST, _normalized_path_key(root_path), "missing"]), {}
            )
        paths: list[tuple[Path, Path]] = []
        discovery_complete = True
        diagnostics: list[ScanDiagnostic] = []
        try:
            for history_root in existing_roots:
                discovered, complete = _discover_jsonl(history_root, active_budget)
                paths.extend((path, history_root) for path in discovered)
                discovery_complete = discovery_complete and complete
        except ScanLimit as exc:
            discovery_complete = False
            diagnostics.append(ScanDiagnostic(str(exc), "history discovery budget was exhausted"))
        if not discovery_complete and not diagnostics:
            diagnostics.append(
                ScanDiagnostic("discovery_incomplete", "history discovery was incomplete")
            )

        metadata: list[SessionMetadata] = []
        skipped = 0
        failed = 0
        for path, history_root in paths:
            try:
                item = _metadata_from_prefix(path, history_root, active_budget)
            except (OSError, ScanLimit) as exc:
                failed += 1
                diagnostics.append(ScanDiagnostic("metadata_unreadable", "session metadata was unreadable"))
                if isinstance(exc, ScanLimit):
                    discovery_complete = False
                    break
                continue
            if item is None:
                failed += 1
                diagnostics.append(ScanDiagnostic("metadata_missing", "session ordering metadata was missing"))
                continue
            if session_id is not None and item.session_id != session_id:
                skipped += 1
                continue
            if not _cwd_matches(root_path, item.cwd):
                skipped += 1
                continue
            if since_dt is not None:
                try:
                    item_time = _parse_iso(item.timestamp) if item.timestamp else None
                except ValueError:
                    item_time = None
                if item_time is None:
                    diagnostics.append(
                        ScanDiagnostic("ordering_unknown", "matching session lacks an ordering timestamp", item.session_id)
                    )
                elif item_time < since_dt:
                    skipped += 1
                    continue
            metadata.append(item)

        for item in metadata:
            try:
                parsed_timestamp = _parse_iso(item.timestamp) if item.timestamp else None
            except ValueError:
                parsed_timestamp = None
            if parsed_timestamp is None and not any(
                diagnostic.code == "ordering_unknown"
                and diagnostic.session_id == item.session_id
                for diagnostic in diagnostics
            ):
                diagnostics.append(
                    ScanDiagnostic(
                        "ordering_unknown", "matching session lacks an ordering timestamp", item.session_id
                    )
                )
        metadata.sort(key=_ordering_key)
        if len(metadata) > MAX_SESSIONS:
            diagnostics.append(ScanDiagnostic("session_limit", "only the newest bounded sessions were scanned"))
            metadata = metadata[:MAX_SESSIONS]
            discovery_complete = False

        candidates: list[RecoveryCandidate] = []
        rejection_counts: Counter[str] = Counter()
        scanned = 0
        stop = False
        for item in metadata:
            if stop:
                break
            try:
                raw_records = list(_bounded_json_lines(item.path, active_budget))
                raw_events, session_diagnostics = _codex_events(
                    item, raw_records, project_root=root_path, home_dir=home
                )
                if active_budget.events + len(raw_events) > MAX_EVENTS:
                    raise ScanLimit("event_limit")
                active_budget.events += len(raw_events)
                result = mine_recoveries(
                    raw_events, project_root=str(root_path), home_dir=str(home)
                )
                scanned += 1
                diagnostics.extend(session_diagnostics)
                if result.degraded:
                    diagnostics.append(
                        ScanDiagnostic("causal_barrier", "session contained a causal barrier", item.session_id)
                    )
                for candidate in result.candidates:
                    if len(candidates) >= MAX_CANDIDATES:
                        raise ScanLimit("candidate_limit")
                    candidates.append(candidate)
                rejection_counts.update(result.rejection_counts)
            except ScanLimit as exc:
                diagnostics.append(ScanDiagnostic(str(exc), "scan budget was exhausted", item.session_id))
                stop = True
                discovery_complete = False
            except OSError:
                failed += 1
                diagnostics.append(ScanDiagnostic("session_unreadable", "session could not be read", item.session_id))

        if len(diagnostics) >= MAX_DIAGNOSTICS:
            diagnostics = diagnostics[: MAX_DIAGNOSTICS - 1]
            diagnostics.append(ScanDiagnostic("diagnostic_limit", "additional diagnostics were omitted"))
            discovery_complete = False
        status = "complete"
        if discovery_complete and session_id is not None and not metadata:
            status = "failed"
        elif discovery_complete and metadata and scanned == 0:
            status = "failed"
        elif not discovery_complete or failed or diagnostics:
            status = "degraded"
        inputs = [
            [item.session_id, item.relative_name, item.path.stat().st_size, item.path.stat().st_mtime_ns]
            for item in metadata[:scanned]
            if item.path.exists()
        ]
        scan_fingerprint = _fingerprint(
            [HISTORY_HOST, ANALYZER_VERSION, _normalized_path_key(root_path), inputs]
        )
        return HistoryScan(
            status, tuple(candidates), tuple(diagnostics), len(metadata), scanned, skipped,
            failed, discovery_complete, scan_fingerprint, dict(rejection_counts)
        )


def validate_interpretation_references(
    root: str | os.PathLike[str],
    evidence: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    home_dir: str | os.PathLike[str] | None = None,
) -> None:
    """Verify reinterpretation roles against one bounded, fully readable source session."""
    source = evidence.get("source")
    roles = replacement.get("causal_roles")
    if not isinstance(source, Mapping) or source.get("host") != HISTORY_HOST:
        raise ValueError("only Codex recovery evidence can currently be reinterpreted")
    if not isinstance(roles, Mapping):
        raise ValueError("reinterpretation causal_roles are required")
    session_id = evidence.get("session_id")
    if not _valid_id(session_id):
        raise ValueError("recovery evidence has an invalid source session")

    root_path = Path(root).expanduser().resolve()
    home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
    budget = ScanBudget()
    history_roots = [home / ".codex" / "sessions", home / ".codex" / "archived_sessions"]
    matches: list[SessionMetadata] = []
    for history_root in history_roots:
        if not history_root.is_dir():
            continue
        paths, complete = _discover_jsonl(history_root, budget)
        if not complete:
            raise ValueError("source-session discovery was incomplete")
        for path in paths:
            metadata = _metadata_from_prefix(path, history_root, budget)
            if (
                metadata is not None
                and metadata.session_id == session_id
                and _cwd_matches(root_path, metadata.cwd)
            ):
                matches.append(metadata)
    if len(matches) != 1:
        raise ValueError("source session is missing or ambiguous")

    raw_records = list(_bounded_json_lines(matches[0].path, budget))
    raw_events, diagnostics = _codex_events(
        matches[0], raw_records, project_root=root_path, home_dir=home
    )
    if diagnostics:
        raise ValueError("source session cannot be verified across a causal barrier")
    events: dict[str, NormalizedEvent] = {}
    for raw in raw_events:
        normalized = raw if isinstance(raw, NormalizedEvent) else normalize_event(
            raw, project_root=str(root_path), home_dir=str(home)
        )
        if _validate_normalized_event(normalized):
            raise ValueError("source session contains an invalid referenced event")
        events[normalized.event_id] = normalized

    failure_id = roles.get("failure_event_id")
    verification_id = roles.get("verification_event_id")
    repair_ids = roles.get("repair_event_ids")
    supporting_ids = roles.get("supporting_event_ids")
    if (
        not isinstance(failure_id, str)
        or not isinstance(verification_id, str)
        or not isinstance(repair_ids, list)
        or not 1 <= len(repair_ids) <= 3
        or any(not isinstance(item, str) for item in repair_ids)
        or not isinstance(supporting_ids, list)
        or len(supporting_ids) > 4
        or any(not isinstance(item, str) for item in supporting_ids)
    ):
        raise ValueError("reinterpretation causal roles are invalid")
    all_ids = [failure_id, *repair_ids, verification_id, *supporting_ids]
    if len(all_ids) != len(set(all_ids)) or any(item not in events for item in all_ids):
        raise ValueError("reinterpretation references missing or duplicate source events")
    failure = events[failure_id]
    repairs = [events[item] for item in repair_ids]
    verification = events[verification_id]
    if not _observable_failure(failure):
        raise ValueError("reinterpretation failure event is not an observable failure")
    if not all(failure.ordinal < item.ordinal < verification.ordinal for item in repairs):
        raise ValueError("reinterpretation repair ordering is invalid")
    if not all(
        failure.ordinal < events[item].ordinal < verification.ordinal
        for item in supporting_ids
    ):
        raise ValueError("reinterpretation supporting-event ordering is invalid")
    if not all(_is_repair(failure, item) for item in repairs):
        raise ValueError("reinterpretation repair events do not address the failure")
    if not _is_verification(failure, repairs, verification):
        raise ValueError("reinterpretation verification does not confirm the repair")


def candidate_id(candidate: RecoveryCandidate) -> str:
    return f"candidate-{candidate.source_fingerprint[:20]}"


def candidate_summary(candidate: RecoveryCandidate) -> dict[str, Any]:
    return {
        "id": candidate_id(candidate),
        "authority": candidate.authority,
        "behavior_delta": candidate.behavior_delta,
        "outcome": "verified_success",
        "reason_codes": list(candidate.reason_codes),
    }


def candidate_detail(candidate: RecoveryCandidate) -> dict[str, Any]:
    return {
        **candidate_summary(candidate),
        "contrast": candidate.contrast,
        "source": {
            "host": HISTORY_HOST,
            "failure_event_id": candidate.failure_id,
            "repair_event_ids": list(candidate.repair_ids),
            "verification_event_id": candidate.verification_id,
            "supporting_event_ids": list(candidate.supporting_ids),
            "source_fingerprint": candidate.source_fingerprint,
            "content_fingerprint": candidate.content_fingerprint,
            "analyzer_version": candidate.analyzer_version,
        },
    }


def render_scan_report(
    scan: HistoryScan,
    *,
    page: int = 1,
    detail_id: str | None = None,
    report_filter: str = "actionable",
    classifications: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if page < 1:
        raise ValueError("page must be at least 1")
    if report_filter not in {"actionable", "new", "reinterpretation"}:
        raise ValueError("unsupported report filter")
    states = classifications or {}
    if detail_id is not None:
        for candidate in scan.candidates:
            if candidate_id(candidate) == detail_id:
                report = {
                    "status": scan.status,
                    "scan_complete": scan.discovery_complete,
                    "scan_fingerprint": scan.scan_fingerprint,
                    "counts": {
                        "selected_sessions": scan.selected_sessions,
                        "scanned_sessions": scan.scanned_sessions,
                        "skipped_sessions": scan.skipped_sessions,
                        "failed_sessions": scan.failed_sessions,
                        "diagnostics": len(scan.diagnostics),
                    },
                    "candidate": {
                        **candidate_detail(candidate),
                        "classification": states.get(candidate.source_fingerprint, "new"),
                    },
                }
                encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
                if len(encoded) > MAX_REPORT_BYTES:
                    raise ValueError("detail report exceeds output budget")
                return report
        raise ValueError(f"candidate detail is unavailable: {detail_id}")

    visible: list[RecoveryCandidate] = []
    unchanged = 0
    reinterpretations = 0
    reconciliations = 0
    authority_reconciliations = 0
    for candidate in scan.candidates:
        state = states.get(candidate.source_fingerprint, "new")
        if state == "unchanged":
            unchanged += 1
            continue
        if state == "reinterpretation_required":
            reinterpretations += 1
        if state == "source_reconciliation_required":
            reconciliations += 1
        if state == "authority_reconciliation_required":
            authority_reconciliations += 1
        if report_filter == "new" and state != "new":
            continue
        if report_filter == "reinterpretation" and state != "reinterpretation_required":
            continue
        visible.append(candidate)
    total_pages = max(1, (len(visible) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > total_pages:
        raise ValueError("requested page is unavailable")
    start = (page - 1) * PAGE_SIZE
    page_items = visible[start : start + PAGE_SIZE]
    diagnostics = scan.diagnostics[:DIAGNOSTIC_PAGE_SIZE]
    report = {
        "status": scan.status,
        "scan_complete": scan.discovery_complete,
        "scan_fingerprint": scan.scan_fingerprint,
        "counts": {
            "selected_sessions": scan.selected_sessions,
            "scanned_sessions": scan.scanned_sessions,
            "skipped_sessions": scan.skipped_sessions,
            "failed_sessions": scan.failed_sessions,
            "actionable": len(visible),
            "unchanged": unchanged,
            "reinterpretation_required": reinterpretations,
            "source_reconciliation_required": reconciliations,
            "authority_reconciliation_required": authority_reconciliations,
            "diagnostics": len(scan.diagnostics),
        },
        "rejection_counts": dict(scan.rejection_counts),
        "candidates": [
            {**candidate_summary(item), "classification": states.get(item.source_fingerprint, "new")}
            for item in page_items
        ],
        "diagnostics": [
            {
                "code": item.code,
                "message": item.message,
                **({"session_id": item.session_id} if item.session_id else {}),
            }
            for item in diagnostics
        ],
        "pagination": {
            "page": page,
            "page_size": PAGE_SIZE,
            "total_visible": len(visible),
            "next_page": page + 1 if page < total_pages else None,
            "omitted_candidates": max(0, len(visible) - len(page_items)),
            "omitted_diagnostics": max(0, len(scan.diagnostics) - len(diagnostics)),
        },
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_COMPACT_REPORT_BYTES:
        raise ValueError("compact report exceeds output budget")
    return report
