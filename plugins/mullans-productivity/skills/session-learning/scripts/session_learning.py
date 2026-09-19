#!/usr/bin/env python3
"""Inspect and validate a project's session-learning store.

The helper is deliberately deterministic and dependency-free. Reasoning about
what a session taught remains the agent's job; this module makes storage,
search, indexing, and validation repeatable.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable
import uuid


SCHEMA_VERSION = 1
EVIDENCE_SCHEMA_VERSION = 2
LESSON_SCHEMA_VERSION = 4
SKILL_VERSION = "0.6.1"
VERSIONED_LESSON_SCHEMA_VERSION = 4
MANIFEST_SCHEMA_VERSION = 2
STORE_RELATIVE = Path(".agents") / "learning"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
SKILL_VERSION_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

LESSON_KINDS = {"guardrail", "workflow", "project_knowledge", "preference", "invariant"}
LESSON_STATUSES = {"candidate", "active", "conflicted", "superseded", "retired"}
DELIVERY_MODES = {"dynamic", "static", "workflow", "automation", "none"}
AUTHORITIES = {"project", "local"}
MANIFEST_ORIGINS = {"current_session", "historical_mining", "maintenance"}
RETRIEVAL_SCHEMA_VERSION = 1
MAX_RETRIEVAL_ENTRIES = 2_000
MAX_RETRIEVAL_BYTES = 1024 * 1024
MAX_VISIBILITY_FILES = 16
MAX_VISIBILITY_FILE_BYTES = 64 * 1024
MAX_VISIBILITY_TOTAL_BYTES = 256 * 1024
WRITER_LOCK_TIMEOUT_SECONDS = 5.0
STATE_SCHEMA_VERSION = 1
CONFIG_SCHEMA_VERSION = 1
DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "retrieval_enabled": True,
    "cooldown_user_prompts": 5,
    "max_lessons_per_event": 3,
    "max_context_characters": 4000,
    "python_path": None,
}
STALE_STATE_SECONDS = 30 * 24 * 60 * 60
ERROR_REPORT_SCHEMA_VERSION = 1
MAX_ERROR_REPORTS = 200
MAX_ERROR_REPORT_BYTES = 512 * 1024
HOSTS = {"codex", "claude", None}
SIGNALS = {
    "explicit_user_correction",
    "test_failure",
    "runtime_failure",
    "ci_failure",
    "review_finding",
    "durable_user_convention",
    "validated_workflow",
    "successful_non_obvious_discovery",
    "recovery_pair",
}


class HookDataError(ValueError):
    """A diagnosable retrieval-data failure that must remain fail-open."""

    def __init__(self, category: str, message: str, *, path: Path | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.path = path


def skill_version_key(version: str) -> tuple[int, int, int]:
    if not SKILL_VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"invalid skill version {version!r}")
    core = version.split("-", 1)[0].split("+", 1)[0]
    major, minor, patch = core.split(".")
    return int(major), int(minor), int(patch)


def _none_delivery() -> dict[str, Any]:
    return {
        "mode": "none",
        "host": None,
        "path": None,
        "instruction_path": None,
        "enforcement_target": None,
    }


def _delivery_from_legacy_destination(
    record: dict[str, Any], authority: str, host: str
) -> dict[str, Any]:
    destination = record.get("destination")
    if not isinstance(destination, dict) or record.get("status") != "active":
        return _none_delivery()
    destination_type = destination.get("type")
    destination_host = destination.get("host")
    destination_path = destination.get("path")
    scope = record.get("scope")
    scope_type = scope.get("type") if isinstance(scope, dict) else None
    if destination_type == "instruction" and scope_type == "repository":
        return {
            "mode": "static",
            "host": destination_host or host,
            "path": destination_path or ("CLAUDE.md" if host == "claude" else "AGENTS.md"),
            "instruction_path": None,
            "enforcement_target": None,
        }
    if destination_type in {"instruction", "index"}:
        instruction_path = destination.get("instruction_path")
        if authority == "local":
            instruction_path = None
        elif not isinstance(instruction_path, str):
            instruction_path = "CLAUDE.md" if host == "claude" else "AGENTS.md"
        return {
            "mode": "dynamic",
            "host": None,
            "path": None,
            "instruction_path": instruction_path,
            "enforcement_target": None,
        }
    if destination_type == "skill":
        return {
            "mode": "workflow",
            "host": destination_host or host,
            "path": destination_path,
            "instruction_path": None,
            "enforcement_target": None,
        }
    if destination_type == "automation":
        return {
            "mode": "automation",
            "host": None,
            "path": None,
            "instruction_path": None,
            "enforcement_target": destination_path,
        }
    return _none_delivery()


def upgrade_lesson_record(
    record: dict[str, Any], *, authority: str, host: str = "codex"
) -> dict[str, Any]:
    """Return the current in-memory form of any supported legacy lesson."""
    version = record.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError("lesson schema_version must be an integer")
    if version < 1:
        raise ValueError(f"unsupported lesson schema_version {version}")
    if version > LESSON_SCHEMA_VERSION:
        raise ValueError(
            f"lesson schema_version {version} is newer than supported version "
            f"{LESSON_SCHEMA_VERSION}"
        )
    migrated = copy.deepcopy(record)
    if version == 1:
        migrated["delivery"] = _delivery_from_legacy_destination(migrated, authority, host)
        migrated.pop("destination", None)
        migrated["schema_version"] = 2
        version = 2
    if version == 2:
        migrated["schema_version"] = 3
        migrated["authority"] = authority
        migrated.setdefault("equivalence_key", None)
        migrated.setdefault("conflict_targets", [])
        migrated.setdefault("conflict_history", [])
        delivery = migrated.get("delivery")
        if authority == "local" and isinstance(delivery, dict) and delivery.get("mode") == "dynamic":
            delivery["instruction_path"] = None
        version = 3
    if version == 3:
        migrated["schema_version"] = VERSIONED_LESSON_SCHEMA_VERSION
        migrated["version"] = SKILL_VERSION
        version = VERSIONED_LESSON_SCHEMA_VERSION
    if version != LESSON_SCHEMA_VERSION:
        raise ValueError(f"no lesson migration registered from schema_version {version}")
    lesson_version = migrated.get("version")
    if not isinstance(lesson_version, str) or not SKILL_VERSION_PATTERN.fullmatch(lesson_version):
        raise ValueError("current lesson schema requires a semantic skill version")
    if lesson_version.split(".", 1)[0] != SKILL_VERSION.split(".", 1)[0]:
        raise ValueError(
            f"lesson version {lesson_version} is outside installed major version "
            f"{SKILL_VERSION.split('.', 1)[0]}"
        )
    return migrated


def lesson_needs_migration(record: dict[str, Any]) -> bool:
    schema = record.get("schema_version")
    if not isinstance(schema, int) or isinstance(schema, bool):
        return False
    if schema < LESSON_SCHEMA_VERSION:
        return True
    if schema != LESSON_SCHEMA_VERSION:
        return False
    version = record.get("version")
    if not isinstance(version, str) or not SKILL_VERSION_PATTERN.fullmatch(version):
        return True
    return skill_version_key(version) < skill_version_key(SKILL_VERSION)

RECOVERY_OPERATIONS = {
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
RECOVERY_STRATEGIES = {
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
MAX_RECOVERY_ID_CHARS = 120
MAX_RECOVERY_TEXT_CHARS = 500
MAX_RECOVERY_EVIDENCE_BYTES = 2500
RECOVERY_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:\b(?:api[_-]?key|token|secret|password|passwd|authorization)\s*[:=]"
    r"|https?://[^/@\s:]+(?::[^/@\s]*)?@"
    r"|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
    r"|\b(?:gh[pousr]_|sk-|xox[baprs]-)[A-Za-z0-9_-]{12,}\b)"
)
RECOVERY_ABSOLUTE_PATH = re.compile(
    r"(?i)(?:(?<![A-Za-z0-9])[a-z]:[/\\][^\s,;]*|(?<![:/\w>])/(?!/)[^\s,;]+)"
)
RECOVERY_HIGH_ENTROPY = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")
RECOVERY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,119}$")
USAGE_COUNTERS = {
    "eligible_sessions",
    "confirmations",
    "violations",
    "repeat_corrections",
}
USAGE_TIMESTAMPS = {
    "last_eligible_at",
    "last_confirmed_at",
    "last_violated_at",
}


def resolve_project_root(explicit_root: str | os.PathLike[str] | None) -> Path:
    """Resolve an explicit root, a Git root, or finally the current directory."""
    if explicit_root is not None:
        return Path(explicit_root).expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if value:
            return Path(value).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return Path.cwd().resolve()


def normalized_project_root(root: str | os.PathLike[str]) -> str:
    value = str(Path(root).expanduser().resolve()).replace("\\", "/").rstrip("/")
    return value.casefold() if os.name == "nt" else value


def project_key(root: str | os.PathLike[str]) -> str:
    return hashlib.sha256(normalized_project_root(root).encode("utf-8")).hexdigest()[:16]


def store_path(
    root: str | os.PathLike[str],
    *,
    authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> Path:
    if authority not in AUTHORITIES:
        raise ValueError("authority must be project or local")
    root_path = Path(root).expanduser().resolve()
    if authority == "project":
        return root_path / STORE_RELATIVE
    home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
    return home / ".agents" / "learning" / "projects" / project_key(root_path)


def authority_stores(
    root: str | os.PathLike[str],
    authority: str,
    *,
    home_dir: str | os.PathLike[str] | None = None,
) -> list[tuple[str, Path]]:
    if authority == "both":
        return [
            (item, store_path(root, authority=item, home_dir=home_dir))
            for item in ("project", "local")
        ]
    if authority not in AUTHORITIES:
        raise ValueError("authority must be project, local, or both")
    return [(authority, store_path(root, authority=authority, home_dir=home_dir))]


def _record_files(store: Path, folder: str) -> list[Path]:
    directory = store / folder
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"), key=lambda path: path.name)


def _read_record(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: record must be a JSON object")
    return value


def _load_records(store: Path, folder: str) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in _record_files(store, folder):
        try:
            record = _read_record(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        record["_path"] = path
        records.append(record)
    return records, errors


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "_path"}


def _tokens(value: Any) -> set[str]:
    if isinstance(value, dict):
        text = " ".join(str(item) for pair in value.items() for item in pair)
    elif isinstance(value, list):
        text = " ".join(str(item) for item in value)
    else:
        text = str(value)
    return set(TOKEN_PATTERN.findall(text.lower()))


def search_lessons(
    root: str | os.PathLike[str], query: str, *, include_all: bool = False,
    authority: str = "project", home_dir: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    """Return lessons ranked by trigger/scope, statement, then general metadata."""
    if authority not in AUTHORITIES | {"both"}:
        raise ValueError("authority must be project, local, or both")
    lessons: list[dict[str, Any]] = []
    load_errors: list[str] = []
    for _, store in authority_stores(root, authority, home_dir=home_dir):
        loaded, errors = _load_records(store, "lessons")
        lessons.extend(loaded)
        load_errors.extend(errors)
    if load_errors:
        raise ValueError("; ".join(load_errors))
    query_tokens = _tokens(query)
    results: list[dict[str, Any]] = []
    for lesson in lessons:
        trigger_scope = _tokens(lesson.get("triggers", [])) | _tokens(lesson.get("scope", {}))
        statement = _tokens(lesson.get("statement", "")) | _tokens(lesson.get("title", ""))
        general = _tokens(
            {
                "kind": lesson.get("kind", ""),
                "status": lesson.get("status", ""),
                "anti_pattern": lesson.get("anti_pattern", []),
                "safe_path": lesson.get("safe_path", []),
            }
        )
        score = (
            5 * len(query_tokens & trigger_scope)
            + 3 * len(query_tokens & statement)
            + len(query_tokens & general)
        )
        if score > 0 or include_all:
            item = _public_record(lesson)
            item["score"] = score
            results.append(item)
    results.sort(
        key=lambda item: (
            -int(item["score"]),
            0 if item.get("authority") == "project" else 1,
            str(item.get("id", "")),
        )
    )
    return results


def _require_fields(record: dict[str, Any], fields: Iterable[str], label: str) -> list[str]:
    return [f"{label}: missing required field '{field}'" for field in fields if field not in record]


def _validate_id(record: dict[str, Any], path: Path, label: str) -> list[str]:
    errors: list[str] = []
    record_id = record.get("id")
    if not isinstance(record_id, str) or not ID_PATTERN.fullmatch(record_id):
        errors.append(f"{label}: id must match {ID_PATTERN.pattern}")
    elif path.stem != record_id:
        errors.append(f"{label}: filename must be {record_id}.json")
    return errors


def _validate_string_list(record: dict[str, Any], field: str, label: str) -> list[str]:
    value = record.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        return [f"{label}: {field} must be a list of non-empty strings"]
    return []


def _validate_relative_path(root: Path, value: Any, label: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{label}: path must be a non-empty relative path"]
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return [f"{label}: path must stay within the project root"]
    try:
        (root / candidate).resolve().relative_to(root.resolve())
    except ValueError:
        return [f"{label}: path must stay within the project root"]
    return []


def _validate_recovery_behavior_delta(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: behavior_delta must be an object"]
    errors: list[str] = []
    if set(value) != {"type", "before", "after"}:
        errors.append(
            f"{label}: behavior_delta must contain only type, before, and after"
        )
    delta_type = value.get("type")
    if delta_type not in {"add", "remove", "replace", "reorder"}:
        errors.append(
            f"{label}: behavior_delta.type must be add, remove, replace, or reorder"
        )
    normalized: dict[str, list[tuple[str, str]]] = {}
    for side in ("before", "after"):
        steps = value.get(side)
        if not isinstance(steps, list) or len(steps) > 3:
            errors.append(
                f"{label}: behavior_delta.{side} must contain at most three ordered steps"
            )
            continue
        normalized_steps: list[tuple[str, str]] = []
        for step in steps:
            if not isinstance(step, dict) or set(step) != {"operation", "strategy"}:
                errors.append(
                    f"{label}: behavior_delta.{side} steps require operation and strategy"
                )
                continue
            operation = step.get("operation")
            strategy = step.get("strategy")
            if operation not in RECOVERY_OPERATIONS or strategy not in RECOVERY_STRATEGIES:
                errors.append(
                    f"{label}: behavior_delta.{side} contains an unsupported step"
                )
                continue
            normalized_steps.append((str(operation), str(strategy)))
        normalized[side] = normalized_steps
    if errors:
        return errors
    before = normalized["before"]
    after = normalized["after"]
    if delta_type == "add" and (before or not after):
        errors.append(
            f"{label}: behavior_delta add requires empty before and non-empty after"
        )
    elif delta_type == "remove" and (not before or after):
        errors.append(
            f"{label}: behavior_delta remove requires non-empty before and empty after"
        )
    elif delta_type == "replace" and (not before or not after or before == after):
        errors.append(
            f"{label}: behavior_delta replace requires distinct non-empty sides"
        )
    elif delta_type == "reorder" and (
        len(before) < 2 or Counter(before) != Counter(after) or before == after
    ):
        errors.append(
            f"{label}: behavior_delta reorder requires the same steps in a different order"
        )
    return errors


def _validate_recovery_source(value: Any, session_id: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: source must be an object for recovery_pair evidence"]
    required = {
        "host",
        "failure_event_id",
        "repair_event_ids",
        "verification_event_id",
        "supporting_event_ids",
        "source_fingerprint",
        "content_fingerprint",
        "analyzer_version",
    }
    errors = _require_fields(value, required, f"{label}: source")
    if set(value) - required:
        errors.append(f"{label}: source contains unsupported fields")
    if value.get("host") not in {"codex", "claude"}:
        errors.append(f"{label}: source.host must be 'codex' or 'claude'")
    failure_id = value.get("failure_event_id")
    verification_id = value.get("verification_event_id")
    for field, item in (
        ("failure_event_id", failure_id),
        ("verification_event_id", verification_id),
    ):
        if not isinstance(item, str) or RECOVERY_ID_PATTERN.fullmatch(item) is None:
            errors.append(
                f"{label}: source.{field} must use safe ID grammar and contain at most "
                f"{MAX_RECOVERY_ID_CHARS} characters"
            )
    repair_ids = value.get("repair_event_ids")
    if (
        not isinstance(repair_ids, list)
        or not 1 <= len(repair_ids) <= 3
        or any(
            not isinstance(item, str) or RECOVERY_ID_PATTERN.fullmatch(item) is None
            for item in repair_ids
        )
    ):
        errors.append(
            f"{label}: source.repair_event_ids must contain one to three event IDs"
        )
    support_ids = value.get("supporting_event_ids")
    if (
        not isinstance(support_ids, list)
        or len(support_ids) > 4
        or any(
            not isinstance(item, str) or RECOVERY_ID_PATTERN.fullmatch(item) is None
            for item in support_ids
        )
    ):
        errors.append(
            f"{label}: source.supporting_event_ids must contain at most four event IDs"
        )
    role_ids = [failure_id, verification_id]
    if isinstance(repair_ids, list):
        role_ids.extend(repair_ids)
    if isinstance(support_ids, list):
        role_ids.extend(support_ids)
    valid_role_ids = [item for item in role_ids if isinstance(item, str) and item]
    if len(valid_role_ids) != len(set(valid_role_ids)):
        errors.append(f"{label}: source event roles must be unique")
    for field in ("source_fingerprint", "content_fingerprint"):
        fingerprint = value.get(field)
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            errors.append(f"{label}: source.{field} must be SHA-256 hex")
    analyzer_version = value.get("analyzer_version")
    if (
        not isinstance(analyzer_version, str)
        or not analyzer_version.strip()
        or len(analyzer_version) > 32
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", analyzer_version) is None
    ):
        errors.append(f"{label}: source.analyzer_version must be a compact version string")
    if not isinstance(session_id, str) or RECOVERY_ID_PATTERN.fullmatch(session_id) is None:
        errors.append(
            f"{label}: top-level session_id must use safe ID grammar and contain at most "
            f"{MAX_RECOVERY_ID_CHARS} characters"
        )
    return errors


def _recovery_privacy_error(
    value: str, *, project_root: Path | None, home_dir: Path | None
) -> bool:
    if re.search(r"[\x00-\x1f\x7f]", value) or RECOVERY_SENSITIVE_TEXT.search(value):
        return True
    normalized = value.replace("\\", "/").lower()
    for raw_prefix in (project_root, home_dir):
        if raw_prefix is None:
            continue
        prefix = str(raw_prefix).replace("\\", "/").rstrip("/").lower()
        if prefix and prefix in normalized:
            return True
    if RECOVERY_ABSOLUTE_PATH.search(value):
        return True
    for match in RECOVERY_HIGH_ENTROPY.finditer(value):
        token = match.group(0)
        categories = sum(
            bool(re.search(pattern, token))
            for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[_+/=-]")
        )
        if categories >= 3:
            return True
    return False


def _validate_evidence_record(
    record: dict[str, Any],
    path: Path,
    *,
    project_root: Path | None = None,
    home_dir: Path | None = None,
) -> list[str]:
    label = str(path)
    errors = _require_fields(
        record,
        {
            "schema_version",
            "record_type",
            "id",
            "authority",
            "session_id",
            "signal",
            "situation",
            "attempted_behavior",
            "feedback",
            "corrected_behavior",
            "outcome",
            "created_at",
        },
        label,
    )
    errors.extend(_validate_id(record, path, label))
    if record.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {EVIDENCE_SCHEMA_VERSION}")
    if record.get("record_type") != "evidence":
        errors.append(f"{label}: record_type must be 'evidence'")
    if record.get("authority") not in AUTHORITIES:
        errors.append(f"{label}: authority must be project or local")
    if record.get("signal") not in SIGNALS:
        errors.append(f"{label}: unsupported signal {record.get('signal')!r}")
    for field in (
        "session_id",
        "situation",
        "attempted_behavior",
        "feedback",
        "corrected_behavior",
        "outcome",
        "created_at",
    ):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")
    if record.get("signal") == "recovery_pair":
        recovery_fields = {
            "schema_version",
            "record_type",
            "id",
            "authority",
            "session_id",
            "signal",
            "situation",
            "attempted_behavior",
            "feedback",
            "corrected_behavior",
            "outcome",
            "created_at",
            "source",
            "behavior_delta",
            "_path",
        }
        if set(record) - recovery_fields:
            errors.append(f"{label}: recovery_pair evidence contains unsupported fields")
        for field in (
            "situation",
            "attempted_behavior",
            "feedback",
            "corrected_behavior",
            "outcome",
        ):
            value = record.get(field)
            if isinstance(value, str) and len(value) > MAX_RECOVERY_TEXT_CHARS:
                errors.append(
                    f"{label}: {field} must contain at most "
                    f"{MAX_RECOVERY_TEXT_CHARS} characters"
                )
            if isinstance(value, str) and _recovery_privacy_error(
                value, project_root=project_root, home_dir=home_dir
            ):
                errors.append(f"{label}: {field} must be normalized and redacted")
        record_id = record.get("id")
        if isinstance(record_id, str) and len(record_id) > MAX_RECOVERY_ID_CHARS:
            errors.append(
                f"{label}: id must contain at most {MAX_RECOVERY_ID_CHARS} characters"
            )
        created_at = record.get("created_at")
        if isinstance(created_at, str) and len(created_at) > 80:
            errors.append(f"{label}: created_at must contain at most 80 characters")
        if "source" not in record:
            errors.append(f"{label}: missing required field 'source'")
        else:
            errors.extend(
                _validate_recovery_source(record.get("source"), record.get("session_id"), label)
            )
        if "behavior_delta" not in record:
            errors.append(f"{label}: missing required field 'behavior_delta'")
        else:
            errors.extend(
                _validate_recovery_behavior_delta(record.get("behavior_delta"), label)
            )
        source = record.get("source")
        if isinstance(source, dict):
            expected_source = _source_fingerprint(
                source.get("host"), record.get("session_id"),
                source.get("failure_event_id"), source.get("verification_event_id"),
            )
            if source.get("source_fingerprint") != expected_source:
                errors.append(f"{label}: source.source_fingerprint does not match recovery endpoints")
            expected_id = f"evidence.recovery.{expected_source[:20]}"
            if record.get("id") != expected_id:
                errors.append(f"{label}: recovery evidence id must be {expected_id}")
            expected_content = _content_fingerprint(
                record.get("feedback"), _source_roles(source), record.get("behavior_delta")
            )
            if source.get("content_fingerprint") != expected_content:
                errors.append(f"{label}: source.content_fingerprint does not match interpretation")
        try:
            evidence_size = len(
                json.dumps(
                    _public_record(record), separators=(",", ":"), ensure_ascii=True
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            errors.append(f"{label}: recovery_pair evidence must be safely serializable")
        else:
            if evidence_size > MAX_RECOVERY_EVIDENCE_BYTES:
                errors.append(
                    f"{label}: recovery_pair evidence must not exceed "
                    f"{MAX_RECOVERY_EVIDENCE_BYTES} bytes"
                )
    return errors


def _validate_usage(value: Any, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: usage must be an object"]
    errors: list[str] = []
    for field in USAGE_COUNTERS:
        counter = value.get(field)
        if not isinstance(counter, int) or isinstance(counter, bool) or counter < 0:
            errors.append(f"{label}: usage.{field} must be a non-negative integer")
    for field in USAGE_TIMESTAMPS:
        timestamp = value.get(field)
        if timestamp is not None and (not isinstance(timestamp, str) or not timestamp.strip()):
            errors.append(f"{label}: usage.{field} must be null or a non-empty string")
    if errors:
        return errors

    eligible = value["eligible_sessions"]
    confirmations = value["confirmations"]
    violations = value["violations"]
    repeat_corrections = value["repeat_corrections"]
    if confirmations + violations > eligible:
        errors.append(
            f"{label}: usage.confirmations + violations cannot exceed eligible_sessions"
        )
    if repeat_corrections > violations:
        errors.append(f"{label}: usage.repeat_corrections cannot exceed violations")
    timestamp_pairs = (
        ("eligible_sessions", "last_eligible_at"),
        ("confirmations", "last_confirmed_at"),
        ("violations", "last_violated_at"),
    )
    for counter_field, timestamp_field in timestamp_pairs:
        counter = value[counter_field]
        timestamp = value[timestamp_field]
        if counter > 0 and timestamp is None:
            errors.append(
                f"{label}: usage.{timestamp_field} is required when {counter_field} is positive"
            )
        if counter == 0 and timestamp is not None:
            errors.append(
                f"{label}: usage.{timestamp_field} must be null when {counter_field} is zero"
            )
    return errors


def _normalized_relative(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def _has_skill_frontmatter(content: str) -> bool:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    try:
        closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return False
    frontmatter = lines[1:closing]
    has_name = any(re.fullmatch(r"name:\s*\S.*", line.strip()) for line in frontmatter)
    has_description = any(
        re.fullmatch(r"description:\s*\S.*", line.strip()) for line in frontmatter
    )
    return has_name and has_description


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _atomic_write_bytes(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


@contextmanager
def writer_lock(
    root: str | os.PathLike[str],
    *,
    authority: str,
    timeout_seconds: float = WRITER_LOCK_TIMEOUT_SECONDS,
) -> Iterable[None]:
    """Serialize writers with an OS-owned handle; no persistent lock file is used."""
    if authority not in AUTHORITIES:
        raise ValueError("authority must be project or local")
    root_path = Path(root).expanduser().resolve()
    deadline = time.monotonic() + timeout_seconds
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        digest = hashlib.sha256(
            f"{normalized_project_root(root_path)}\0{authority}".encode("utf-8")
        ).hexdigest()
        handle = kernel32.CreateMutexW(None, False, f"Local\\session-learning-{digest}")
        if not handle:
            raise OSError(ctypes.get_last_error(), "unable to create session-learning mutex")
        acquired = False
        try:
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            result = kernel32.WaitForSingleObject(handle, remaining)
            if result not in {0x00000000, 0x00000080}:
                if result == 0x00000102:
                    raise TimeoutError("session-learning writer lock is busy; retry")
                raise OSError(ctypes.get_last_error(), "unable to wait for session-learning mutex")
            acquired = True
            yield
        finally:
            if acquired:
                kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
        return

    try:
        import fcntl
    except ImportError as exc:
        raise OSError("OS-managed writer locking is unavailable") from exc
    descriptor = os.open(root_path, os.O_RDONLY)
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("session-learning writer lock is busy; retry")
                time.sleep(0.01)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _within_root(root: Path, target: Path) -> Path:
    resolved = target.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"transaction target escapes project root: {target}") from exc
    return resolved


def apply_file_transaction(
    root: str | os.PathLike[str],
    changes: dict[Path, bytes | None],
    *,
    validator: Any | None = None,
    transaction_store: Path | None = None,
) -> list[Path]:
    """Atomically replace a set of project files and roll back on failure.

    Individual replacements are atomic. A short-lived journal and snapshots make
    the multi-file operation recoverable when validation or a later write fails.
    """
    root_path = Path(root).resolve()
    journal_store = transaction_store.resolve() if transaction_store is not None else store_path(root_path)
    recover_transactions(root_path, transaction_store=journal_store)
    normalized = {
        _within_root(root_path, Path(path)): content for path, content in changes.items()
    }
    normalized = {
        target: content
        for target, content in normalized.items()
        if (content is None and target.exists())
        or (
            content is not None
            and (not target.exists() or target.read_bytes() != content)
        )
    }
    if not normalized:
        return []

    transaction_root = journal_store / ".transactions"
    transaction_dir = transaction_root / uuid.uuid4().hex
    transaction_dir.mkdir(parents=True, exist_ok=False)
    originals: dict[Path, bytes | None] = {}
    journal_entries: list[dict[str, Any]] = []
    try:
        for index, target in enumerate(sorted(normalized, key=lambda item: str(item))):
            original = target.read_bytes() if target.exists() else None
            originals[target] = original
            relative = target.relative_to(root_path).as_posix()
            backup_name = None
            if original is not None:
                backup_name = f"{index:04d}.bak"
                _atomic_write_bytes(transaction_dir / backup_name, original)
            journal_entries.append(
                {
                    "path": relative,
                    "existed": original is not None,
                    "backup": backup_name,
                    "original_sha256": _sha256_bytes(original) if original is not None else None,
                    "replacement_sha256": (
                        _sha256_bytes(normalized[target])
                        if normalized[target] is not None
                        else None
                    ),
                }
            )
        _atomic_write_bytes(
            transaction_dir / "journal.json",
            _json_bytes({"transaction_schema_version": 1, "files": journal_entries}),
        )

        for target in sorted(normalized, key=lambda item: str(item)):
            content = normalized[target]
            if content is None:
                if target.exists():
                    target.unlink()
            else:
                _atomic_write_bytes(target, content)

        validation_errors = list(validator() if validator is not None else [])
        if validation_errors:
            raise ValueError("; ".join(str(item) for item in validation_errors))
    except BaseException:
        for target, original in originals.items():
            if original is None:
                if target.exists():
                    target.unlink()
            else:
                _atomic_write_bytes(target, original)
        raise
    finally:
        shutil.rmtree(transaction_dir, ignore_errors=True)
        try:
            transaction_root.rmdir()
        except OSError:
            pass
    return sorted(normalized, key=lambda item: str(item))


def recover_transactions(
    root: str | os.PathLike[str], *, transaction_store: Path | None = None
) -> int:
    """Roll back transactions whose journal survived an interrupted process."""
    root_path = Path(root).resolve()
    journal_store = transaction_store.resolve() if transaction_store is not None else store_path(root_path)
    transaction_root = journal_store / ".transactions"
    if not transaction_root.is_dir():
        return 0
    recovered = 0
    for transaction_dir in sorted(
        (path for path in transaction_root.iterdir() if path.is_dir()), key=lambda path: path.name
    ):
        journal_path = transaction_dir / "journal.json"
        if not journal_path.exists():
            shutil.rmtree(transaction_dir)
            continue
        try:
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot recover transaction {transaction_dir}: {exc}") from exc
        if not isinstance(journal, dict) or journal.get("transaction_schema_version") != 1:
            raise ValueError(f"cannot recover transaction {transaction_dir}: unsupported journal")
        entries = journal.get("files")
        if not isinstance(entries, list):
            raise ValueError(f"cannot recover transaction {transaction_dir}: invalid file list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError(f"cannot recover transaction {transaction_dir}: invalid entry")
            target = _within_root(root_path, root_path / entry["path"])
            if entry.get("existed"):
                backup_name = entry.get("backup")
                original_sha256 = entry.get("original_sha256")
                if not isinstance(backup_name, str) or not isinstance(original_sha256, str):
                    raise ValueError(f"cannot recover transaction {transaction_dir}: missing backup")
                backup = _within_root(transaction_dir, transaction_dir / backup_name)
                backup_bytes = backup.read_bytes()
                if _sha256_bytes(backup_bytes) != original_sha256:
                    raise ValueError(
                        f"cannot recover transaction {transaction_dir}: backup hash mismatch"
                    )
                _atomic_write_bytes(target, backup_bytes)
            elif target.exists():
                target.unlink()
        shutil.rmtree(transaction_dir)
        recovered += 1
    try:
        transaction_root.rmdir()
    except OSError:
        pass
    return recovered


def _instruction_pointer_block() -> str:
    return (
        "<!-- session-learning:index -->\n"
        "- Project-specific learned context is indexed at `.agents/learning/index.md`. "
        "When a task matches a listed path, scope, or trigger, load only the matching "
        "active lesson records; candidates are not instructions.\n"
    )


def _remove_marker_block(content: str, marker: str) -> str:
    lines = content.splitlines(keepends=True)
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if marker not in line:
            kept.append(line)
            index += 1
            continue
        standalone_comment = line.strip().startswith("<!--")
        index += 1
        if standalone_comment and index < len(lines) and lines[index].lstrip().startswith("-"):
            index += 1
    result = "".join(kept)
    result = re.sub(r"\n{3,}", "\n\n", result).rstrip()
    return result + "\n" if result else ""


def _ensure_pointer(content: str) -> str:
    if "session-learning:index" in content:
        return content
    base = content.rstrip()
    return (base + "\n\n" if base else "") + _instruction_pointer_block()


def _remove_pointer(content: str) -> str:
    return _remove_marker_block(content, "session-learning:index")


def _all_lesson_records_with_replacements(
    store: Path, replacements: dict[Path, dict[str, Any]]
) -> list[dict[str, Any]]:
    lessons, errors = _load_records(store, "lessons")
    if errors:
        raise ValueError("; ".join(errors))
    return [replacements.get(Path(item["_path"]), _public_record(item)) for item in lessons]


def _ensure_claude_bridge(root: Path) -> dict[Path, bytes | None]:
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not agents.exists():
        return {}
    current = claude.read_text(encoding="utf-8") if claude.exists() else ""
    if re.search(r"(?m)^@(?:\./)?AGENTS\.md\s*$", current):
        return {}
    updated = "@AGENTS.md\n" if not current.strip() else f"@AGENTS.md\n\n{current.lstrip()}"
    return {claude: updated.encode("utf-8")}


def _needs_claude_bridge(root: Path) -> bool:
    lessons, errors = _load_records(store_path(root), "lessons")
    if errors:
        raise ValueError("; ".join(errors))
    for lesson in lessons:
        delivery = lesson.get("delivery")
        if lesson.get("status") != "active" or not isinstance(delivery, dict):
            continue
        if delivery.get("instruction_path") == "AGENTS.md":
            return True
        if delivery.get("mode") == "static" and delivery.get("path") == "AGENTS.md":
            return True
    return False


def activate_store(root: str | os.PathLike[str], *, host: str = "auto") -> dict[str, Any]:
    resolved_host = host
    if host == "auto":
        if os.environ.get("PLUGIN_ROOT"):
            resolved_host = "codex"
        elif os.environ.get("CLAUDE_PLUGIN_ROOT"):
            resolved_host = "claude"
        else:
            resolved_host = "codex"
    root_path = Path(root).resolve()
    with writer_lock(root_path, authority="project"):
        lessons, errors = _load_records(store_path(root_path), "lessons")
        if errors:
            raise ValueError("; ".join(errors))
        if not lessons:
            return {"changed": False, "files": []}
        extra: dict[Path, bytes | None] = _derived_changes(
            store_path(root_path), [_public_record(item) for item in lessons], authority="project"
        )
        for item in lessons:
            delivery = item.get("delivery")
            if (
                item.get("status") == "active"
                and isinstance(delivery, dict)
                and delivery.get("mode") == "dynamic"
                and isinstance(delivery.get("instruction_path"), str)
            ):
                pointer = root_path / delivery["instruction_path"]
                current = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
                extra[pointer] = _ensure_pointer(current).encode("utf-8")
        if resolved_host == "both" and _needs_claude_bridge(root_path):
            extra.update(_ensure_claude_bridge(root_path))
        written = apply_file_transaction(
            root_path, extra, validator=lambda: validate_store(root_path)
        )
    return {
        "changed": bool(written),
        "files": [path.relative_to(root_path).as_posix() for path in written],
    }


def _load_lesson_by_id(
    root: Path, lesson_id: str, *, authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    path = store_path(root, authority=authority, home_dir=home_dir) / "lessons" / f"{lesson_id}.json"
    if not path.is_file():
        raise ValueError(f"lesson not found: {lesson_id}")
    return path, _read_record(path)


def _changes_for_lesson_update(
    root: Path, lesson_path: Path, record: dict[str, Any], old_record: dict[str, Any]
) -> dict[Path, bytes | None]:
    changes: dict[Path, bytes | None] = {lesson_path: _json_bytes(record)}
    old_delivery = old_record.get("delivery")
    if isinstance(old_delivery, dict) and old_delivery.get("mode") in {"static", "workflow"}:
        projection_path = old_delivery.get("path")
        if isinstance(projection_path, str):
            target = root / projection_path
            if target.exists():
                updated = _remove_marker_block(
                    target.read_text(encoding="utf-8"), f"session-learning:{record['id']}"
                )
                changes[target] = updated.encode("utf-8")
    lessons = _all_lesson_records_with_replacements(store_path(root), {lesson_path: record})
    active_dynamic = any(
        item.get("status") == "active"
        and isinstance(item.get("delivery"), dict)
        and item["delivery"].get("mode") == "dynamic"
        for item in lessons
    )
    pointer_paths = {
        root / str(item["delivery"].get("instruction_path"))
        for item in lessons
        if isinstance(item.get("delivery"), dict)
        and item["delivery"].get("instruction_path")
    }
    if not active_dynamic:
        for pointer in pointer_paths | {root / "AGENTS.md", root / "CLAUDE.md"}:
            if pointer.exists():
                current = (
                    changes[pointer].decode("utf-8")
                    if pointer in changes and changes[pointer] is not None
                    else pointer.read_text(encoding="utf-8")
                )
                updated = _remove_pointer(current)
                if updated != current:
                    changes[pointer] = updated.encode("utf-8")
    changes[store_path(root) / "index.md"] = render_index(lessons).encode("utf-8")
    return changes


def deactivate_lesson(
    root: str | os.PathLike[str], lesson_id: str, *, authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    lesson_path, old_record = _load_lesson_by_id(
        root_path, lesson_id, authority=authority, home_dir=home_dir
    )
    operations = [
        {"op": "set_status", "value": "retired"},
        {"op": "set_delivery_none"},
    ]
    if old_record.get("conflict_targets"):
        operations.append({"op": "clear_conflict_targets"})
    return apply_manifest(
        root_path,
        {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "origin": "maintenance",
            "changes": [{
                "path": f".agents/learning/lessons/{lesson_path.name}",
                "lesson_patch": {
                    "expected_sha256": canonical_record_sha256(old_record),
                    "intent": "retire", "operations": operations,
                },
            }],
        },
        authority=authority, home_dir=home_dir,
    )


def reconcile_delivery(
    root: str | os.PathLike[str], *, host: str, apply: bool = False
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    lessons, errors = _load_records(store_path(root_path), "lessons")
    if errors:
        raise ValueError("; ".join(errors))
    missing_static: list[str] = []
    for item in lessons:
        delivery = item.get("delivery")
        if item.get("status") != "active" or not isinstance(delivery, dict):
            continue
        if delivery.get("mode") != "static" or delivery.get("host") != host:
            continue
        path_value = delivery.get("path")
        target = root_path / str(path_value)
        marker = f"session-learning:{item.get('id')}"
        if not target.exists() or marker not in target.read_text(encoding="utf-8"):
            missing_static.append(str(item.get("id")))
    if apply:
        for lesson_id in missing_static:
            set_delivery(root_path, lesson_id, "static", host=host)
    return {"missing_static": sorted(missing_static), "changed": bool(apply and missing_static)}


def set_delivery(
    root: str | os.PathLike[str], lesson_id: str, mode: str, *, host: str = "codex",
    authority: str = "project", home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    allowed = {"dynamic", "static"} if authority == "project" else {"dynamic", "none"}
    if mode not in allowed:
        raise ValueError(f"set-delivery mode for {authority} must be one of {sorted(allowed)}")
    if host not in {"codex", "claude"}:
        raise ValueError("host must be codex or claude")
    root_path = Path(root).resolve()
    lesson_path, old_record = _load_lesson_by_id(
        root_path, lesson_id, authority=authority, home_dir=home_dir
    )
    if old_record.get("status") != "active":
        raise ValueError("only active lessons can change delivery mode")
    if mode == "dynamic":
        delivery = {
            "mode": "dynamic",
            "host": None,
            "path": None,
            "instruction_path": (
                None if authority == "local" else "CLAUDE.md" if host == "claude" else "AGENTS.md"
            ),
            "enforcement_target": None,
        }
    elif mode == "static":
        projection_path = "CLAUDE.md" if host == "claude" else "AGENTS.md"
        delivery = {
            "mode": "static",
            "host": host,
            "path": projection_path,
            "instruction_path": None,
            "enforcement_target": None,
        }
    else:
        delivery = _none_delivery()
    return apply_manifest(
        root_path,
        {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "origin": "maintenance",
            "changes": [{
                "path": f".agents/learning/lessons/{lesson_path.name}",
                "lesson_patch": {
                    "expected_sha256": canonical_record_sha256(old_record),
                    "intent": "set_delivery",
                    "operations": [{"op": "set_delivery", "value": delivery}],
                },
            }],
        },
        authority=authority, home_dir=home_dir,
    )


def reactivate_lesson(
    root: str | os.PathLike[str], lesson_id: str, *, authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Move a retired lesson back to candidate so the retrospective can re-gate it."""
    root_path = Path(root).resolve()
    lesson_path, old_record = _load_lesson_by_id(
        root_path, lesson_id, authority=authority, home_dir=home_dir
    )
    if old_record.get("status") != "retired":
        raise ValueError("only retired lessons can be reactivated")
    return apply_manifest(
        root_path,
        {
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "origin": "maintenance",
            "changes": [{
                "path": f".agents/learning/lessons/{lesson_path.name}",
                "lesson_patch": {
                    "expected_sha256": canonical_record_sha256(old_record),
                    "intent": "reactivate",
                    "operations": [
                        {"op": "set_status", "value": "candidate"},
                        {"op": "set_delivery_none"},
                    ],
                },
            }],
        },
        authority=authority, home_dir=home_dir,
    )


LESSON_OPERATION_ORDER = (
    "append_provenance",
    "replace_statement",
    "replace_scope",
    "append_triggers",
    "append_exception",
    "replace_anti_pattern",
    "replace_safe_path",
    "set_status",
    "set_delivery",
    "set_delivery_none",
    "set_conflict_targets",
    "clear_conflict_targets",
    "append_relationship",
)
INTENT_OPERATIONS: dict[str, set[str]] = {
    "measure": set(),
    "confirm": {"append_provenance"},
    "narrow": {"replace_scope", "replace_statement", "append_triggers"},
    "extend": {"replace_scope", "replace_statement", "append_triggers"},
    "revise_scope": {"replace_scope", "replace_statement", "append_triggers"},
    "add_exception": {"append_exception", "replace_statement"},
    "replace_action": {"replace_safe_path", "replace_statement", "replace_anti_pattern"},
    "promote": {"set_status", "set_delivery", "append_provenance"},
    "resolve_conflict": {
        "replace_statement", "replace_scope", "append_triggers", "append_exception",
        "replace_anti_pattern", "replace_safe_path", "set_status", "set_delivery",
        "set_delivery_none", "clear_conflict_targets", "append_provenance",
    },
    "supersede": {
        "append_provenance", "set_status", "set_delivery_none", "append_relationship"
    },
    "set_delivery": {"set_delivery"},
    "retire": {"set_status", "set_delivery_none", "clear_conflict_targets"},
    "reactivate": {"set_status", "set_delivery_none"},
}


def _none_delivery() -> dict[str, Any]:
    return {
        "mode": "none", "host": None, "path": None,
        "instruction_path": None, "enforcement_target": None,
    }


def canonical_record_sha256(record: dict[str, Any]) -> str:
    return _sha256_bytes(_json_bytes(record))


def _literal_scope_set(scope: Any) -> tuple[str, set[str]] | None:
    if not isinstance(scope, dict) or scope.get("type") not in {"repository", "paths", "subsystem"}:
        return None
    paths = scope.get("paths")
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        return None
    normalized = {_normalized_relative(item).casefold() for item in paths}
    if any(any(token in item for token in ("*", "?", "[")) for item in normalized):
        return None
    return str(scope["type"]), normalized


def _validate_scope_intent(intent: str, before: Any, after: Any) -> None:
    if intent not in {"narrow", "extend"}:
        return
    old = _literal_scope_set(before)
    new = _literal_scope_set(after)
    if old is None or new is None:
        raise ValueError(f"{intent} requires literal, provable scope containment")
    old_type, old_paths = old
    new_type, new_paths = new
    if intent == "narrow":
        valid = (
            (old_type == new_type and new_paths < old_paths)
            or (old_type == "repository" and new_type in {"paths", "subsystem"} and bool(new_paths))
        )
    else:
        valid = (
            (old_type == new_type and old_paths < new_paths)
            or (old_type in {"paths", "subsystem"} and new_type == "repository")
        )
    if not valid:
        raise ValueError(f"{intent} does not make the required strict scope change")


def _scope_pattern(value: str) -> tuple[str, str] | None:
    normalized = _normalized_relative(value).casefold().rstrip("/")
    if not normalized or any(token in normalized for token in ("?", "[")):
        return None
    if normalized.endswith("/**") and "*" not in normalized[:-3]:
        return "prefix", normalized[:-3].rstrip("/")
    if "*" not in normalized:
        return "exact", normalized
    return None


def scopes_proven_disjoint(first: Any, second: Any) -> bool:
    if not isinstance(first, dict) or not isinstance(second, dict):
        return False
    if first.get("type") == "repository" or second.get("type") == "repository":
        return False
    first_paths = first.get("paths")
    second_paths = second.get("paths")
    if not isinstance(first_paths, list) or not first_paths or not isinstance(second_paths, list) or not second_paths:
        return False
    for raw_first in first_paths:
        for raw_second in second_paths:
            left = _scope_pattern(str(raw_first))
            right = _scope_pattern(str(raw_second))
            if left is None or right is None:
                return False
            left_kind, left_value = left
            right_kind, right_value = right
            if left_kind == right_kind == "exact":
                disjoint = left_value != right_value
            elif left_kind == "prefix" and right_kind == "prefix":
                disjoint = not (
                    left_value == right_value
                    or left_value.startswith(right_value + "/")
                    or right_value.startswith(left_value + "/")
                )
            elif left_kind == "prefix":
                disjoint = not (
                    right_value == left_value or right_value.startswith(left_value + "/")
                )
            else:
                disjoint = not (
                    left_value == right_value or left_value.startswith(right_value + "/")
                )
            if not disjoint:
                return False
    return True


def _apply_operation(record: dict[str, Any], operation: dict[str, Any]) -> None:
    name = operation["op"]
    value = operation.get("value")
    if name == "append_provenance":
        if not isinstance(value, dict):
            raise ValueError("append_provenance requires an object")
        if value not in record["provenance"]:
            record["provenance"].append(copy.deepcopy(value))
    elif name == "replace_statement":
        record["statement"] = value
    elif name == "replace_scope":
        record["scope"] = copy.deepcopy(value)
    elif name == "append_triggers":
        values = value if isinstance(value, list) else [value]
        if any(not isinstance(item, str) or not item.strip() for item in values):
            raise ValueError("append_triggers requires non-empty strings")
        record["triggers"] = list(dict.fromkeys([*record["triggers"], *values]))
    elif name == "append_exception":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("append_exception requires non-empty text")
        if value not in record["exceptions"]:
            record["exceptions"].append(value)
    elif name in {"replace_anti_pattern", "replace_safe_path"}:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"{name} requires a list of non-empty strings")
        record["anti_pattern" if name == "replace_anti_pattern" else "safe_path"] = value
    elif name == "set_status":
        record["status"] = value
    elif name == "set_delivery":
        record["delivery"] = copy.deepcopy(value)
    elif name == "set_delivery_none":
        record["delivery"] = _none_delivery()
    elif name == "set_conflict_targets":
        if not isinstance(value, list) or not value or len(value) != len(set(value)):
            raise ValueError("set_conflict_targets requires unique lesson IDs")
        record["conflict_targets"] = list(value)
        record["conflict_history"] = list(
            dict.fromkeys([*record.get("conflict_history", []), *value])
        )
    elif name == "clear_conflict_targets":
        record["conflict_targets"] = []
    elif name == "append_relationship":
        if (
            not isinstance(value, dict)
            or value.get("type") not in {"supersedes", "related"}
            or not isinstance(value.get("lesson_id"), str)
        ):
            raise ValueError("append_relationship requires a supported type and lesson_id")
        values = record["relationships"][value["type"]]
        if value["lesson_id"] not in values:
            values.append(value["lesson_id"])
    else:
        raise ValueError(f"unsupported lesson patch operation: {name}")


def _validate_usage_update(record: dict[str, Any], update: Any, origin: str) -> None:
    if origin != "current_session":
        raise ValueError("usage updates are allowed only for current_session origin")
    if not isinstance(update, dict) or not update:
        raise ValueError("usage_update must be a non-empty object")
    allowed = USAGE_COUNTERS | USAGE_TIMESTAMPS
    if set(update) - allowed:
        raise ValueError("usage_update contains unsupported fields")
    usage = record["usage"]
    timestamp_for = {
        "eligible_sessions": "last_eligible_at",
        "confirmations": "last_confirmed_at",
        "violations": "last_violated_at",
        "repeat_corrections": "last_violated_at",
    }
    changed_counter = False
    for counter in USAGE_COUNTERS:
        if counter not in update:
            continue
        value = update[counter]
        if not isinstance(value, int) or isinstance(value, bool) or value <= usage[counter]:
            raise ValueError(f"usage_update.{counter} must increase monotonically")
        if timestamp_for[counter] not in update:
            raise ValueError(f"usage_update.{counter} requires {timestamp_for[counter]}")
        usage[counter] = value
        changed_counter = True
    for timestamp in USAGE_TIMESTAMPS:
        if timestamp in update:
            if not isinstance(update[timestamp], str) or not update[timestamp].strip():
                raise ValueError(f"usage_update.{timestamp} must be a timestamp")
            usage[timestamp] = update[timestamp]
    if not changed_counter:
        raise ValueError("usage_update must increase at least one counter")


def apply_lesson_patch(old: dict[str, Any], patch: Any, *, origin: str) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise ValueError("lesson_patch must be an object")
    required = {"expected_sha256", "intent", "operations"}
    if not required.issubset(patch) or set(patch) - (
        required | {"usage_update", "equivalence_update"}
    ):
        raise ValueError("lesson_patch has invalid fields")
    if patch["expected_sha256"] != canonical_record_sha256(old):
        raise ValueError("stale lesson patch: expected_sha256 does not match")
    intent = patch.get("intent")
    if intent not in INTENT_OPERATIONS:
        raise ValueError(f"unsupported lesson patch intent: {intent}")
    operations = patch.get("operations")
    if not isinstance(operations, list):
        raise ValueError("lesson_patch.operations must be a list")
    names = [item.get("op") for item in operations if isinstance(item, dict)]
    if len(names) != len(operations) or len(names) != len(set(names)):
        raise ValueError("lesson patch operations must be named and unique")
    if set(names) - INTENT_OPERATIONS[intent]:
        raise ValueError(f"intent {intent} does not permit the requested operations")
    required_operations = {
        "confirm": {"append_provenance"},
        "narrow": {"replace_scope"},
        "extend": {"replace_scope"},
        "revise_scope": {"replace_scope"},
        "add_exception": {"append_exception"},
        "replace_action": {"replace_safe_path"},
        "promote": {"set_status", "set_delivery"},
        "resolve_conflict": {"set_status", "clear_conflict_targets"},
        "supersede": {"set_status", "set_delivery_none"},
        "set_delivery": {"set_delivery"},
        "retire": {"set_status", "set_delivery_none"},
        "reactivate": {"set_status", "set_delivery_none"},
    }
    missing_operations = required_operations.get(str(intent), set()) - set(names)
    if missing_operations:
        raise ValueError(
            f"intent {intent} requires operations: {', '.join(sorted(missing_operations))}"
        )
    by_name = {item["op"]: item for item in operations}
    result = copy.deepcopy(old)
    previous_scope = copy.deepcopy(old.get("scope"))
    for name in LESSON_OPERATION_ORDER:
        if name in by_name:
            _apply_operation(result, by_name[name])
    if "replace_scope" in by_name:
        _validate_scope_intent(str(intent), previous_scope, result.get("scope"))

    old_status = old.get("status")
    if intent == "measure" and "usage_update" not in patch:
        raise ValueError("measure requires usage_update")
    if intent == "confirm" and names != ["append_provenance"]:
        raise ValueError("confirm requires append_provenance")
    lifecycle = {
        "promote": ("candidate", "active"),
        "resolve_conflict": ("conflicted", result.get("status")),
        "retire": ({"active", "candidate", "conflicted"}, "retired"),
        "reactivate": ("retired", "candidate"),
        "supersede": ({"active", "candidate"}, "superseded"),
    }
    if intent in lifecycle:
        expected_old, expected_new = lifecycle[intent]
        valid_old = old_status in expected_old if isinstance(expected_old, set) else old_status == expected_old
        if not valid_old or result.get("status") != expected_new:
            raise ValueError(f"{intent} lifecycle preconditions are not satisfied")
    if intent == "resolve_conflict" and result.get("status") not in {"active", "retired"}:
        raise ValueError("resolve_conflict must activate or retire the lesson")
    if intent in {"retire", "resolve_conflict"} and result.get("status") == "retired" and result.get("conflict_targets"):
        raise ValueError("retired conflict resolution must clear conflict_targets")
    if intent == "reactivate" and result.get("delivery", {}).get("mode") != "none":
        raise ValueError("reactivate must leave delivery disabled")
    if intent == "set_delivery" and old_status != "active":
        raise ValueError("set_delivery requires an active lesson")
    if "usage_update" in patch:
        _validate_usage_update(result, patch["usage_update"], origin)
    if "equivalence_update" in patch:
        update = patch["equivalence_update"]
        if (
            not isinstance(update, dict)
            or set(update) != {"value", "rationale"}
            or not isinstance(update.get("rationale"), str)
            or not update["rationale"].strip()
        ):
            raise ValueError("equivalence_update requires value and reconciliation rationale")
        value = update.get("value")
        if value is not None and (
            not isinstance(value, str) or not ID_PATTERN.fullmatch(value) or value != value.casefold()
        ):
            raise ValueError("equivalence_update value must be null or a lowercase stable key")
        result["equivalence_key"] = value
    if result != old:
        result["timestamps"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return result


def _content_fingerprint(contrast: Any, causal_roles: Any, behavior_delta: Any) -> str:
    value = {"contrast": contrast, "causal_roles": causal_roles, "behavior_delta": behavior_delta}
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_fingerprint(
    host: Any, session_id: Any, failure_event_id: Any, verification_event_id: Any
) -> str:
    encoded = json.dumps(
        [host, session_id, failure_event_id, verification_event_id],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_roles(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "failure_event_id": source.get("failure_event_id"),
        "repair_event_ids": source.get("repair_event_ids"),
        "verification_event_id": source.get("verification_event_id"),
        "supporting_event_ids": source.get("supporting_event_ids"),
    }


def _normalize_new_evidence(record: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    if result.get("signal") != "recovery_pair":
        return result
    source = result.get("source")
    if not isinstance(source, dict):
        return result
    source_fingerprint = _source_fingerprint(
        source.get("host"), result.get("session_id"),
        source.get("failure_event_id"), source.get("verification_event_id"),
    )
    expected_id = f"evidence.recovery.{source_fingerprint[:20]}"
    if result.get("id") != expected_id:
        raise ValueError(f"recovery evidence id must be {expected_id}")
    source["source_fingerprint"] = source_fingerprint
    source["content_fingerprint"] = _content_fingerprint(
        result.get("feedback"), _source_roles(source), result.get("behavior_delta")
    )
    result["source"] = source
    return result


def apply_evidence_patch(
    old: dict[str, Any], patch: Any, *, verify_references: Any | None = None
) -> dict[str, Any]:
    if not isinstance(patch, dict) or set(patch) != {"expected_sha256", "replace_interpretation"}:
        raise ValueError("evidence_patch must contain expected_sha256 and replace_interpretation")
    if patch["expected_sha256"] != canonical_record_sha256(old):
        raise ValueError("stale evidence patch: expected_sha256 does not match")
    replacement = patch["replace_interpretation"]
    required = {"contrast", "causal_roles", "behavior_delta", "analyzer_version"}
    if not isinstance(replacement, dict) or set(replacement) != required:
        raise ValueError("replace_interpretation has invalid fields")
    roles = replacement["causal_roles"]
    role_fields = {
        "failure_event_id", "repair_event_ids", "verification_event_id", "supporting_event_ids"
    }
    if not isinstance(roles, dict) or set(roles) != role_fields:
        raise ValueError("causal_roles has invalid fields")
    source = copy.deepcopy(old.get("source"))
    if not isinstance(source, dict):
        raise ValueError("only recovery evidence can be reinterpreted")
    if roles["failure_event_id"] != source.get("failure_event_id") or roles["verification_event_id"] != source.get("verification_event_id"):
        raise ValueError("evidence reinterpretation cannot change recovery endpoints")
    if verify_references is not None:
        verify_references(old, replacement)
    result = copy.deepcopy(old)
    result["feedback"] = replacement["contrast"]
    result["behavior_delta"] = copy.deepcopy(replacement["behavior_delta"])
    for key in role_fields:
        source[key] = copy.deepcopy(roles[key])
    fingerprint = _content_fingerprint(
        replacement["contrast"], roles, replacement["behavior_delta"]
    )
    old_fingerprint = source.get("content_fingerprint")
    if fingerprint == old_fingerprint:
        return old
    source["content_fingerprint"] = fingerprint
    source["analyzer_version"] = replacement["analyzer_version"]
    result["source"] = source
    return result


def _verify_evidence_reinterpretation(
    project_root: Path,
    home_dir: str | os.PathLike[str] | None,
    old: dict[str, Any],
    replacement: dict[str, Any],
) -> None:
    history = _load_history_module()
    history.validate_interpretation_references(
        project_root,
        old,
        replacement,
        home_dir=home_dir,
    )


def _inherit_supersession_conflicts(lessons: list[dict[str, Any]]) -> None:
    by_id = {str(item.get("id")): item for item in lessons}
    for replacement in lessons:
        if replacement.get("status") != "active":
            continue
        supersedes = replacement.get("relationships", {}).get("supersedes", [])
        inherited: list[str] = []
        for target_id in supersedes:
            target = by_id.get(str(target_id))
            if target is not None:
                inherited.extend(str(item) for item in target.get("conflict_history", []))
        if inherited:
            replacement["conflict_history"] = list(
                dict.fromkeys([*replacement.get("conflict_history", []), *inherited])
            )


def _validate_proposed_state(lessons: list[dict[str, Any]]) -> None:
    by_id = {str(item.get("id")): item for item in lessons}
    active_keys: Counter[str] = Counter(
        str(item["equivalence_key"])
        for item in lessons
        if item.get("status") == "active" and item.get("equivalence_key") is not None
    )
    duplicates = [key for key, count in active_keys.items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate active equivalence_key: {', '.join(sorted(duplicates))}")
    replacement_targets = {
        str(target)
        for item in lessons
        if item.get("status") == "active"
        for target in item.get("relationships", {}).get("supersedes", [])
    }
    for item in lessons:
        lesson_id = str(item.get("id"))
        if item.get("status") == "superseded" and lesson_id not in replacement_targets:
            raise ValueError(f"{lesson_id}: superseded lesson requires an active replacement")
        if item.get("status") != "active":
            continue
        for target_id in item.get("conflict_history", []):
            target = by_id.get(str(target_id))
            if target is None:
                raise ValueError(f"{lesson_id}: missing historical conflict target {target_id}")
            if target.get("status") in {"retired", "superseded"}:
                continue
            if not scopes_proven_disjoint(item.get("scope"), target.get("scope")):
                raise ValueError(f"{lesson_id}: unresolved conflict with {target_id}")


def _manifest_target(
    project_root: Path, store: Path, relative_value: str, authority: str
) -> tuple[Path, str | None]:
    normalized = relative_value.replace("\\", "/")
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsupported transaction path: {relative_value}")
    match = re.fullmatch(r"\.agents/learning/(lessons|evidence|cases)/([^/]+\.json)", normalized)
    if match:
        target = _within_root(store, store / match.group(1) / match.group(2))
        return target, match.group(1)
    if authority == "local":
        raise ValueError(f"local manifests accept only logical learning-record paths: {relative_value}")
    if relative.name in {"AGENTS.md", "CLAUDE.md"} or re.fullmatch(
        r"\.(agents|claude)/skills/[^/]+/SKILL\.md", normalized
    ):
        return _within_root(project_root, project_root / relative), None
    raise ValueError(f"unsupported transaction path: {relative_value}")


def apply_manifest(
    root: str | os.PathLike[str],
    manifest: dict[str, Any],
    *,
    authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Apply one authority-scoped, typed authoring manifest transactionally."""
    if authority not in AUTHORITIES:
        raise ValueError("apply-manifest requires project or local authority")
    if not isinstance(manifest, dict) or manifest.get("manifest_schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"manifest_schema_version must be {MANIFEST_SCHEMA_VERSION}")
    origin = manifest.get("origin")
    if origin not in MANIFEST_ORIGINS:
        raise ValueError("manifest origin must be current_session, historical_mining, or maintenance")
    entries = manifest.get("changes")
    if not isinstance(entries, list) or not entries:
        return {
            "changed": False, "authority": authority, "changes": [],
            "validation": "passed", "actionable_deferrals": [], "files": [],
        }
    project_root = Path(root).expanduser().resolve()
    store = store_path(project_root, authority=authority, home_dir=home_dir)
    confinement = project_root if authority == "project" else store
    with writer_lock(project_root, authority=authority):
        recover_transactions(confinement, transaction_store=store)
        lessons, lesson_errors = _load_records(store, "lessons")
        evidence_records, evidence_errors = _load_records(store, "evidence")
        cases, case_errors = _load_records(store, "cases")
        if lesson_errors or evidence_errors or case_errors:
            raise ValueError("; ".join(lesson_errors + evidence_errors + case_errors))
        prospective_lessons = {Path(item["_path"]): _public_record(item) for item in lessons}
        original_lessons = copy.deepcopy(prospective_lessons)
        prospective_evidence = {Path(item["_path"]): _public_record(item) for item in evidence_records}
        changes: dict[Path, bytes | None] = {}
        summaries: list[dict[str, Any]] = []
        seen_targets: set[Path] = set()
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ValueError("each manifest change requires a logical relative path")
            target, folder = _manifest_target(project_root, store, entry["path"], authority)
            if target in seen_targets:
                raise ValueError(f"duplicate manifest target: {entry['path']}")
            seen_targets.add(target)
            variants = [
                key for key in ("json", "content", "delete", "lesson_patch", "evidence_patch")
                if key in entry
            ]
            if len(variants) != 1:
                raise ValueError(f"manifest change for {entry['path']} requires exactly one payload")
            variant = variants[0]
            existing = target.exists()
            if folder == "lessons":
                old: dict[str, Any] | None = None
                if existing and variant != "lesson_patch":
                    raise ValueError("existing lessons require a hash-guarded lesson_patch")
                if not existing and variant != "json":
                    raise ValueError("new lessons require a complete JSON record")
                if variant == "lesson_patch":
                    old = prospective_lessons.get(target)
                    if old is None:
                        raise ValueError(f"lesson not found: {target.stem}")
                    record = apply_lesson_patch(old, entry[variant], origin=origin)
                else:
                    record = copy.deepcopy(entry["json"])
                    if isinstance(record, dict):
                        record["schema_version"] = LESSON_SCHEMA_VERSION
                        record["version"] = SKILL_VERSION
                if not isinstance(record, dict) or record.get("authority") != authority:
                    raise ValueError("lesson authority must match the selected store")
                prospective_lessons[target] = record
                if old is None or record != old:
                    changes[target] = _json_bytes(record)
                usage_deltas = {
                    counter: int(record.get("usage", {}).get(counter, 0))
                    - int(old.get("usage", {}).get(counter, 0) if old is not None else 0)
                    for counter in sorted(USAGE_COUNTERS)
                    if int(record.get("usage", {}).get(counter, 0))
                    != int(old.get("usage", {}).get(counter, 0) if old is not None else 0)
                }
                summaries.append(
                    {"id": record.get("id"), "record_type": "lesson", "status": record.get("status"),
                     "delivery": record.get("delivery", {}).get("mode"),
                     "usage_deltas": usage_deltas}
                )
                continue
            if folder == "evidence":
                old = None
                if existing and variant != "evidence_patch":
                    raise ValueError("existing recovery evidence requires an evidence_patch")
                if not existing and variant != "json":
                    raise ValueError("new evidence requires a complete JSON record")
                if variant == "evidence_patch":
                    old = prospective_evidence.get(target)
                    if old is None:
                        raise ValueError(f"evidence not found: {target.stem}")
                    record = apply_evidence_patch(
                        old,
                        entry[variant],
                        verify_references=lambda old_record, replacement: (
                            _verify_evidence_reinterpretation(
                                project_root, home_dir, old_record, replacement
                            )
                        ),
                    )
                else:
                    record = _normalize_new_evidence(entry["json"])
                if not isinstance(record, dict) or record.get("authority") != authority:
                    raise ValueError("evidence authority must match the selected store")
                prospective_evidence[target] = record
                if old is None or record != old:
                    changes[target] = _json_bytes(record)
                summaries.append({"id": record.get("id"), "record_type": "evidence"})
                continue
            if folder == "cases":
                if variant != "json" or not isinstance(entry["json"], dict):
                    raise ValueError("case changes require a complete JSON record")
                changes[target] = _json_bytes(entry["json"])
                summaries.append({"id": entry["json"].get("id"), "record_type": "case"})
                continue
            if variant == "content":
                if not isinstance(entry["content"], str):
                    raise ValueError("manifest content must be text")
                changes[target] = entry["content"].encode("utf-8")
            elif variant == "delete" and entry["delete"] is True:
                changes[target] = None
            else:
                raise ValueError("projection changes require content or delete")

        proposed_lesson_values = list(prospective_lessons.values())
        _inherit_supersession_conflicts(proposed_lesson_values)
        for target, record in prospective_lessons.items():
            old = original_lessons.get(target)
            if old is None or record != old:
                changes[target] = _json_bytes(record)
        if any(
            isinstance(entry, dict)
            and isinstance(entry.get("lesson_patch"), dict)
            and "usage_update" in entry["lesson_patch"]
            for entry in entries
        ) and any(
            isinstance(entry, dict)
            and isinstance(entry.get("json"), dict)
            and entry["json"].get("record_type") == "evidence"
            and entry["json"].get("signal") == "recovery_pair"
            and isinstance(entry["json"].get("source"), dict)
            and entry["json"]["source"].get("host")
            for entry in entries
        ):
            raise ValueError("usage updates cannot accompany mined recovery evidence")
        _validate_proposed_state(proposed_lesson_values)
        if authority == "project":
            for target, record in prospective_lessons.items():
                old = original_lessons.get(target)
                if old is None or old == record:
                    continue
                projection_updates = _changes_for_lesson_update(
                    project_root, target, record, old
                )
                projection_updates.pop(target, None)
                projection_updates.pop(store / "index.md", None)
                changes.update(projection_updates)
            for record in proposed_lesson_values:
                delivery = record.get("delivery")
                if record.get("status") != "active" or not isinstance(delivery, dict):
                    continue
                if delivery.get("mode") == "dynamic" and isinstance(
                    delivery.get("instruction_path"), str
                ):
                    pointer = project_root / delivery["instruction_path"]
                    current = (
                        changes[pointer].decode("utf-8")
                        if pointer in changes and changes[pointer] is not None
                        else pointer.read_text(encoding="utf-8") if pointer.exists() else ""
                    )
                    updated = _ensure_pointer(current)
                    if updated != current:
                        changes[pointer] = updated.encode("utf-8")
                if delivery.get("mode") in {"static", "workflow"} and isinstance(
                    delivery.get("path"), str
                ):
                    projection = project_root / delivery["path"]
                    marker = f"session-learning:{record.get('id')}"
                    current = (
                        changes[projection].decode("utf-8")
                        if projection in changes and changes[projection] is not None
                        else projection.read_text(encoding="utf-8") if projection.exists() else ""
                    )
                    if marker not in current:
                        base = current.rstrip()
                        block = f"<!-- {marker} -->\n- {' '.join(str(record.get('statement', '')).split())}\n"
                        changes[projection] = ((base + "\n\n" if base else "") + block).encode("utf-8")
        changes.update(_derived_changes(store, proposed_lesson_values, authority=authority))
        written = apply_file_transaction(
            confinement,
            changes,
            transaction_store=store,
            validator=lambda: validate_store(
                project_root, authority=authority, home_dir=home_dir
            ),
        )
        return {
            "changed": bool(written),
            "authority": authority,
            "changes": summaries if written else [],
            "validation": "passed",
            "actionable_deferrals": [],
            "files": [path.relative_to(confinement).as_posix() for path in written],
        }


def find_learning_root(
    cwd: str | os.PathLike[str],
    *,
    home_dir: str | os.PathLike[str] | None = None,
) -> Path | None:
    start = Path(cwd).expanduser().resolve()
    candidates = [start, *start.parents]
    for candidate in candidates:
        project_store = store_path(candidate, authority="project", home_dir=home_dir)
        local_store = store_path(candidate, authority="local", home_dir=home_dir)
        if project_store.is_dir() or local_store.is_dir():
            return candidate
    return None


def _load_config(root: Path, home_dir: Path) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    for path in (
        home_dir / ".agents" / "session-learning" / "config.json",
        store_path(root) / "config.json",
    ):
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or value.get("schema_version") != CONFIG_SCHEMA_VERSION:
            continue
        for key in DEFAULT_CONFIG:
            if key in value:
                config[key] = value[key]
    if not isinstance(config.get("retrieval_enabled"), bool):
        config["retrieval_enabled"] = True
    for key, default in (
        ("cooldown_user_prompts", 5),
        ("max_lessons_per_event", 3),
        ("max_context_characters", 4000),
    ):
        value = config.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            config[key] = default
    python_path = config.get("python_path")
    if (
        not isinstance(python_path, str)
        or not Path(python_path).is_absolute()
        or not Path(python_path).is_file()
    ):
        config["python_path"] = None
    return config


def _project_hash(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).casefold().encode("utf-8")).hexdigest()[:16]


def _state_path(data_dir: Path, root: Path, session_id: str) -> Path:
    project_hash = _project_hash(root)
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return data_dir / f"state-{project_hash}-{session_hash}.json"


def _diagnostic_file(path: Path | None, root: Path, home: Path) -> str | None:
    if path is None:
        return None
    resolved = path.expanduser().resolve(strict=False)
    for base in (root, home):
        try:
            return resolved.relative_to(base.resolve()).as_posix()
        except ValueError:
            continue
    return resolved.name or None


def _lesson_versions(path: Path | None) -> tuple[str | None, int | None]:
    if (
        path is None
        or path.suffix.casefold() != ".json"
        or path.parent.name != "lessons"
        or not path.is_file()
    ):
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "unknown", None
    if not isinstance(value, dict) or value.get("record_type") != "lesson":
        return None, None
    schema = value.get("schema_version")
    schema_version = schema if isinstance(schema, int) and not isinstance(schema, bool) else None
    lesson_version = value.get("version")
    if isinstance(lesson_version, str) and lesson_version.strip():
        return lesson_version, schema_version
    return "legacy", schema_version


def _error_category(exc: Exception) -> str:
    if isinstance(exc, HookDataError):
        return exc.category
    if isinstance(exc, PermissionError):
        return "permissions"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json"
    if isinstance(exc, OSError):
        return "io"
    if isinstance(exc, (TypeError, ValueError, KeyError)):
        return "invalid_data"
    return "engine"


def _exception_type(exc: Exception) -> str:
    if isinstance(exc, HookDataError) and isinstance(exc.__cause__, Exception):
        return type(exc.__cause__).__name__
    return type(exc).__name__


def _error_message(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return f"Invalid JSON at line {exc.lineno}, column {exc.colno}."
    if isinstance(exc, OSError):
        return exc.strerror or "The operating system rejected the file operation."
    if isinstance(exc, HookDataError):
        return str(exc)[:300]
    return "Unexpected error during advisory lesson retrieval."


def _prune_error_reports(directory: Path) -> None:
    try:
        reports = sorted(
            (item for item in directory.glob("*.json") if item.is_file()),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        retained_bytes = 0
        for index, report in enumerate(reports):
            size = report.stat().st_size
            if index >= MAX_ERROR_REPORTS or retained_bytes + size > MAX_ERROR_REPORT_BYTES:
                report.unlink()
            else:
                retained_bytes += size
    except OSError:
        return


def _record_hook_error(
    exc: Exception,
    *,
    payload: dict[str, Any],
    root: Path,
    data_dir: Path,
    home: Path,
    operation: str,
) -> None:
    """Persist one privacy-safe, fingerprinted report; never raise to the hook."""
    try:
        raw_path = getattr(exc, "path", None) or getattr(exc, "filename", None)
        path = Path(raw_path) if isinstance(raw_path, (str, os.PathLike)) else None
        lesson_version, lesson_schema = _lesson_versions(path)
        identity = {
            "category": _error_category(exc),
            "exception_type": _exception_type(exc),
            "hook_event": str(payload.get("hook_event_name", "unknown")),
            "operation": operation,
            "project_hash": _project_hash(root),
            "file": _diagnostic_file(path, root, home),
            "skill_version": SKILL_VERSION,
            "lesson_version": lesson_version,
            "lesson_schema_version": lesson_schema,
            "error_code": getattr(exc, "errno", None),
        }
        fingerprint = hashlib.sha256(_json_bytes(identity)).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        report = {
            "report_schema_version": ERROR_REPORT_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            **identity,
            "message": _error_message(exc),
            "first_seen": now,
            "last_seen": now,
            "occurrences": 1,
        }
        directories = [
            home / ".agents" / "session-learning" / "errors" / identity["project_hash"],
            data_dir / "errors" / identity["project_hash"],
        ]
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                target = directory / f"{fingerprint}.json"
                with _state_lock(target, timeout_seconds=0.25):
                    is_new = not target.is_file()
                    if not is_new:
                        try:
                            previous = json.loads(target.read_text(encoding="utf-8"))
                        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                            previous = None
                        if isinstance(previous, dict):
                            report["first_seen"] = previous.get("first_seen", now)
                            count = previous.get("occurrences")
                            report["occurrences"] = (
                                count + 1
                                if isinstance(count, int) and not isinstance(count, bool) and count >= 1
                                else 1
                            )
                    _atomic_write_bytes(target, _json_bytes(report))
                if is_new:
                    _prune_error_reports(directory)
                return
            except (OSError, TimeoutError):
                continue
    except Exception:
        return


def _load_hook_error_reports(
    root: Path,
    *,
    home: Path,
    data_dir: str | os.PathLike[str] | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    project_hash = _project_hash(root)
    directories = [home / ".agents" / "session-learning" / "errors" / project_hash]
    resolved_data = data_dir or os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if resolved_data:
        directories.append(Path(resolved_data).expanduser().resolve() / "errors" / project_hash)
    by_fingerprint: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for directory in dict.fromkeys(directories):
        if not directory.is_dir():
            continue
        try:
            candidates = list(directory.glob("*.json"))
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
            continue
        for path in candidates[: MAX_ERROR_REPORTS + 1]:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"{path}: {exc}")
                continue
            fingerprint = value.get("fingerprint") if isinstance(value, dict) else None
            if not isinstance(fingerprint, str) or path.stem != fingerprint:
                errors.append(f"{path}: invalid hook error report")
                continue
            previous = by_fingerprint.get(fingerprint)
            if previous is None or str(value.get("last_seen", "")) > str(
                previous.get("last_seen", "")
            ):
                by_fingerprint[fingerprint] = value
    reports = sorted(
        by_fingerprint.values(), key=lambda item: str(item.get("last_seen", "")), reverse=True
    )
    return reports, sorted(errors)


@contextmanager
def _state_lock(state_path: Path, *, timeout_seconds: float = 1.5) -> Iterable[None]:
    lock_path = state_path.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > 10:
                    lock_path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for hook state lock")
            time.sleep(0.01)
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        try:
            lock_path.unlink()
        except OSError:
            pass


def _new_state() -> dict[str, Any]:
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "prompt_sequence": 0,
        "delivered": {},
        "relevant": [],
        "drift_notified": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _new_state()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _new_state()
    if not isinstance(value, dict) or value.get("state_schema_version") != STATE_SCHEMA_VERSION:
        return _new_state()
    state = _new_state()
    if isinstance(value.get("prompt_sequence"), int):
        state["prompt_sequence"] = max(0, value["prompt_sequence"])
    if isinstance(value.get("delivered"), dict):
        state["delivered"] = {
            str(key): int(sequence)
            for key, sequence in value["delivered"].items()
            if isinstance(key, str) and isinstance(sequence, int)
        }
    for key in ("relevant", "drift_notified"):
        if isinstance(value.get(key), list):
            state[key] = [str(item) for item in value[key] if isinstance(item, str)]
    return state


def _save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_write_bytes(path, _json_bytes(state))


def _prune_stale_states(data_dir: Path, *, now: float | None = None) -> None:
    cutoff = (now if now is not None else datetime.now(timezone.utc).timestamp()) - STALE_STATE_SECONDS
    try:
        candidates = list(data_dir.glob("state-*.json"))
    except OSError:
        return
    for candidate in candidates:
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:
            continue


def _normalize_text(value: str) -> str:
    return " ".join(TOKEN_PATTERN.findall(value.casefold()))


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _string_values(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _string_values(nested)]
    return []


def _relative_event_paths(root: Path, tool_input: Any) -> list[str]:
    paths: list[str] = []
    if not isinstance(tool_input, dict):
        return paths
    for key, value in tool_input.items():
        if "path" not in str(key).casefold() and "file" not in str(key).casefold():
            continue
        for item in _string_values(value):
            candidate = Path(item)
            try:
                relative = candidate.resolve().relative_to(root) if candidate.is_absolute() else candidate
            except (OSError, ValueError):
                continue
            paths.append(_normalized_relative(str(relative)))
    return paths


def _load_retrieval_catalog(
    store: Path, authority: str, *, report_errors: bool = False
) -> list[dict[str, Any]]:
    transaction_root = store / ".transactions"
    try:
        if transaction_root.is_dir() and any(transaction_root.iterdir()):
            return []
    except OSError:
        return []
    path = store / "retrieval.json"
    try:
        if not path.is_file():
            return []
        if path.stat().st_size > MAX_RETRIEVAL_BYTES:
            if report_errors:
                raise HookDataError(
                    "invalid_catalog", "Retrieval catalog exceeds its size limit.", path=path
                )
            return []
        raw = path.read_bytes()
        if len(raw) > MAX_RETRIEVAL_BYTES:
            if report_errors:
                raise HookDataError(
                    "invalid_catalog", "Retrieval catalog exceeds its size limit.", path=path
                )
            return []
        value = json.loads(raw)
    except HookDataError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        if report_errors:
            raise HookDataError(
                "invalid_catalog", "Retrieval catalog is unreadable or malformed.", path=path
            ) from exc
        return []
    if not isinstance(value, dict) or value.get("schema_version") != RETRIEVAL_SCHEMA_VERSION:
        if report_errors:
            raise HookDataError(
                "invalid_catalog", "Retrieval catalog has an unsupported schema.", path=path
            )
        return []
    lessons = value.get("lessons")
    if not isinstance(lessons, list) or len(lessons) > MAX_RETRIEVAL_ENTRIES:
        if report_errors:
            raise HookDataError(
                "invalid_catalog", "Retrieval catalog entries are invalid.", path=path
            )
        return []
    required = {
        "id", "authority", "title", "statement", "scope", "triggers", "safe_path",
        "exceptions", "equivalence_key", "delivery",
    }
    if any(
        not isinstance(item, dict)
        or set(item) != required
        or item.get("authority") != authority
        for item in lessons
    ):
        if report_errors:
            raise HookDataError(
                "invalid_catalog", "Retrieval catalog contains an invalid lesson entry.", path=path
            )
        return []
    if _json_bytes({"schema_version": RETRIEVAL_SCHEMA_VERSION, "lessons": lessons}) != raw:
        if report_errors:
            raise HookDataError(
                "invalid_catalog", "Retrieval catalog is not canonical.", path=path
            )
        return []
    return lessons


def _path_matches(pattern: str, value: str) -> bool:
    normalized_pattern = _normalized_relative(pattern).casefold()
    normalized_value = _normalized_relative(value).casefold()
    return fnmatch.fnmatchcase(normalized_value, normalized_pattern)


def _lesson_score(
    lesson: dict[str, Any], *, text: str, event_paths: list[str], tool_input: Any
) -> int:
    score = 0
    scope = lesson.get("scope")
    scope_paths = scope.get("paths", []) if isinstance(scope, dict) else []
    if any(
        _path_matches(str(pattern), event_path)
        for pattern in scope_paths
        for event_path in event_paths
    ):
        score += 100
    normalized_text = _normalize_text(text)
    for trigger in lesson.get("triggers", []) if isinstance(lesson.get("triggers"), list) else []:
        normalized_trigger = _normalize_text(str(trigger))
        if normalized_trigger and normalized_trigger in normalized_text:
            score += 50
    operation_text = _normalize_text(" ".join(_string_values(tool_input)))
    operation_terms = _normalize_text(" ".join(str(item) for item in lesson.get("safe_path", [])))
    if operation_text and len(_tokens(operation_text) & _tokens(operation_terms)) >= 2:
        score += 25
    if score:
        statement_tokens = _tokens(lesson.get("statement", "")) | _tokens(lesson.get("title", ""))
        score += len(_tokens(normalized_text) & statement_tokens)
    return score


def _bounded_instruction_text(path: Path, visibility: dict[str, Any]) -> str | None:
    cache = visibility.setdefault("cache", {})
    key = str(path.resolve())
    if key in cache:
        return cache[key]
    if len(cache) >= MAX_VISIBILITY_FILES:
        cache[key] = None
        return None
    try:
        size = path.stat().st_size
        if size > MAX_VISIBILITY_FILE_BYTES:
            cache[key] = None
            return None
        if visibility.get("bytes", 0) + size > MAX_VISIBILITY_TOTAL_BYTES:
            cache[key] = None
            return None
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        cache[key] = None
        return None
    visibility["bytes"] = visibility.get("bytes", 0) + size
    cache[key] = content
    return content


def _claude_imports_agents(
    root: Path, cwd: Path, agents_path: Path, visibility: dict[str, Any]
) -> bool:
    current = cwd.resolve()
    for directory in [current, *current.parents]:
        try:
            directory.relative_to(root)
        except ValueError:
            break
        claude = directory / "CLAUDE.md"
        if claude.is_file():
            content = _bounded_instruction_text(claude, visibility)
            if content is None:
                return False
            for match in re.finditer(r"(?m)^@(\.?\.?[/\\][^\r\n]+|[^\r\n]+)$", content):
                imported = (directory / match.group(1).strip()).resolve()
                if imported == agents_path.resolve():
                    return True
        if directory == root:
            break
    return False


def _static_visible(
    lesson: dict[str, Any], root: Path, cwd: Path, host: str,
    visibility: dict[str, Any] | None = None,
) -> bool:
    delivery = lesson.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("mode") != "static":
        return False
    path_value = delivery.get("path")
    if not isinstance(path_value, str):
        return False
    projection = root / path_value
    marker = f"session-learning:{lesson.get('id')}"
    active_visibility = visibility if visibility is not None else {"cache": {}, "bytes": 0}
    content = _bounded_instruction_text(projection, active_visibility)
    if content is None or marker not in content:
        return False
    try:
        cwd.resolve().relative_to(projection.parent.resolve())
    except ValueError:
        return False
    if delivery.get("host") == host:
        return True
    if host == "claude" and projection.name == "AGENTS.md":
        return _claude_imports_agents(root, cwd, projection, active_visibility)
    return False


def _hook_context(
    event_name: str, lessons: list[dict[str, Any]], limit: int, maximum: int | None = None
) -> dict[str, Any]:
    if not lessons:
        return {}
    header = "Relevant session lessons:\n"
    parts = [header]
    emitted: list[str] = []
    for lesson in lessons:
        if maximum is not None and len(emitted) >= maximum:
            break
        safe_path = lesson.get("safe_path")
        safe = "; ".join(str(item) for item in safe_path) if isinstance(safe_path, list) else ""
        exceptions = lesson.get("exceptions")
        exception_text = (
            "; ".join(" ".join(str(item).split()) for item in exceptions)
            if isinstance(exceptions, list) else ""
        )
        line = (
            f"- [{lesson.get('authority')}:{lesson.get('id')}] "
            f"{' '.join(str(lesson.get('statement', '')).split())}"
        )
        if safe:
            line += f" Safe path: {safe}."
        if exception_text:
            line += f" Exceptions: {exception_text}."
        line += "\n"
        if sum(len(item) for item in parts) + len(line) > limit:
            continue
        parts.append(line)
        emitted.append(f"{lesson.get('authority')}:{lesson.get('id')}")
    if len(parts) == 1:
        return {}
    return {
        "_emitted": emitted,
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": "".join(parts).rstrip(),
        }
    }


def _handle_hook_event_unlocked(
    payload: dict[str, Any],
    *,
    host: str,
    data_dir: str | os.PathLike[str],
    home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return advisory context for one Codex or Claude hook event."""
    if host not in {"codex", "claude"} or not isinstance(payload, dict):
        return {}
    event_name = str(payload.get("hook_event_name", ""))
    cwd_value = payload.get("cwd")
    session_id = payload.get("session_id")
    if not isinstance(cwd_value, str) or not isinstance(session_id, str):
        return {}
    home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
    root = find_learning_root(cwd_value, home_dir=home)
    if root is None:
        return {}
    data_path = Path(data_dir).expanduser().resolve()
    state_path = _state_path(data_path, root, session_id)
    if event_name == "SessionEnd":
        try:
            state_path.unlink()
        except OSError:
            pass
        _prune_stale_states(data_path)
        return {}
    config = _load_config(root, home)
    if not config["retrieval_enabled"]:
        return {}
    state = _load_state(state_path)
    source = str(payload.get("source", ""))
    if event_name == "SessionStart" and source in {"startup", "fork", "clear"}:
        state = _new_state()
        _save_state(state_path, state)
        return {}

    bypass_cooldown = event_name == "SessionStart" and source in {"compact", "resume"}
    text = ""
    event_paths: list[str] = []
    if bypass_cooldown:
        pass
    elif event_name in {"UserPromptSubmit", "PreToolUse"}:
        if event_name == "UserPromptSubmit":
            state["prompt_sequence"] += 1
            text = str(payload.get("prompt", ""))
        else:
            text = " ".join(_string_values(payload.get("tool_input")))
        event_paths = _relative_event_paths(root, payload.get("tool_input"))
    active: list[dict[str, Any]] = []
    for authority in ("project", "local"):
        try:
            active.extend(
                _load_retrieval_catalog(
                    store_path(root, authority=authority, home_dir=home),
                    authority,
                    report_errors=True,
                )
            )
        except Exception as exc:
            _record_hook_error(
                exc,
                payload=payload,
                root=root,
                data_dir=data_path,
                home=home,
                operation=f"load_{authority}_retrieval_catalog",
            )
    by_identity = {
        f"{item.get('authority')}:{item.get('id')}": item for item in active
    }

    selected: list[dict[str, Any]] = []
    if bypass_cooldown:
        selected = [by_identity[item] for item in state["relevant"] if item in by_identity]
    elif event_name in {"UserPromptSubmit", "PreToolUse"}:
        scored: list[tuple[int, dict[str, Any]]] = []
        cwd = Path(cwd_value)
        visibility: dict[str, Any] = {"cache": {}, "bytes": 0}
        for lesson in active:
            if lesson.get("authority") == "project" and _static_visible(
                lesson, root, cwd, host, visibility
            ):
                continue
            score = _lesson_score(
                lesson, text=text, event_paths=event_paths, tool_input=payload.get("tool_input")
            )
            if score < 25:
                continue
            identity = f"{lesson.get('authority')}:{lesson.get('id')}"
            last = state["delivered"].get(identity)
            cooldown = int(config["cooldown_user_prompts"])
            if isinstance(last, int) and state["prompt_sequence"] - last < cooldown:
                continue
            scored.append((score, lesson))
        scored.sort(
            key=lambda item: (
                -item[0],
                0 if item[1].get("authority") == "project" else 1,
                str(item[1].get("id", "")),
            )
        )
        project_equivalence = {
            item.get("equivalence_key")
            for _, item in scored
            if item.get("authority") == "project" and item.get("equivalence_key") is not None
        }
        selected = [
            item for _, item in scored
            if not (
                item.get("authority") == "local"
                and item.get("equivalence_key") is not None
                and item.get("equivalence_key") in project_equivalence
            )
        ]

    maximum = int(config["max_lessons_per_event"])
    result = _hook_context(
        event_name, selected, int(config["max_context_characters"]), maximum
    )
    if result:
        emitted = set(result.pop("_emitted", []))
        selected = [
            lesson for lesson in selected
            if f"{lesson.get('authority')}:{lesson.get('id')}" in emitted
        ]
        drift_ids = [
            f"{lesson.get('authority')}:{lesson.get('id')}"
            for lesson in selected
            if isinstance(lesson.get("delivery"), dict)
            and lesson["delivery"].get("mode") == "static"
            and f"{lesson.get('authority')}:{lesson.get('id')}" not in state["drift_notified"]
        ]
        if drift_ids:
            result["systemMessage"] = (
                "Session Learning detected an unavailable static projection and "
                "delivered it dynamically: " + ", ".join(drift_ids)
            )
            state["drift_notified"].extend(drift_ids)
        for lesson in selected:
            identity = f"{lesson.get('authority')}:{lesson.get('id')}"
            state["delivered"][identity] = state["prompt_sequence"]
            if identity not in state["relevant"]:
                state["relevant"].append(identity)
    _save_state(state_path, state)
    return result


def handle_hook_event(
    payload: dict[str, Any],
    *,
    host: str,
    data_dir: str | os.PathLike[str],
    home_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Serialize per-session state updates and fail open on lock contention."""
    if host not in {"codex", "claude"} or not isinstance(payload, dict):
        return {}
    cwd_value = payload.get("cwd")
    session_id = payload.get("session_id")
    if not isinstance(cwd_value, str) or not isinstance(session_id, str):
        return {}
    root = find_learning_root(cwd_value, home_dir=home_dir)
    if root is None:
        return {}
    state_path = _state_path(Path(data_dir).expanduser().resolve(), root, session_id)
    try:
        with _state_lock(state_path):
            return _handle_hook_event_unlocked(
                payload, host=host, data_dir=data_dir, home_dir=home_dir
            )
    except Exception as exc:
        # Retrieval is advisory. A malformed cache, lesson catalog, or unexpected
        # runtime condition must never block the host action that invoked the hook.
        _record_hook_error(
            exc,
            payload=payload,
            root=root,
            data_dir=Path(data_dir).expanduser().resolve(),
            home=(
                Path(home_dir).expanduser().resolve()
                if home_dir is not None
                else Path.home()
            ),
            operation="process_hook_event",
        )
        return {}


def _validate_delivery(
    root: Path,
    value: Any,
    status: Any,
    kind: Any,
    lesson_id: Any,
    label: str,
    authority: str = "project",
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: delivery must be an object"]
    errors: list[str] = []
    required = {"mode", "host", "path", "instruction_path", "enforcement_target"}
    errors.extend(_require_fields(value, required, f"{label}: delivery"))
    mode = value.get("mode")
    host = value.get("host")
    path_value = value.get("path")
    instruction_path = value.get("instruction_path")
    enforcement_target = value.get("enforcement_target")
    if mode not in DELIVERY_MODES:
        errors.append(f"{label}: unsupported delivery mode {mode!r}")
    if host not in HOSTS:
        errors.append(f"{label}: delivery.host must be 'codex', 'claude', or null")
    if authority == "local" and mode not in {"dynamic", "none"}:
        errors.append(f"{label}: local lessons support only dynamic or none delivery")

    if status != "active" and mode != "none":
        errors.append(f"{label}: inactive lessons require delivery mode 'none'")
    if status == "active":
        expected_modes = {
            "guardrail": {"dynamic", "static"},
            "preference": {"dynamic", "static"},
            "project_knowledge": {"dynamic"},
            "workflow": {"workflow"},
            "invariant": {"automation", "dynamic"},
        }
        if (
            kind in expected_modes
            and mode not in expected_modes[kind]
            and not (authority == "local" and mode == "none")
        ):
            expected = ", ".join(sorted(expected_modes[kind]))
            errors.append(f"{label}: active {kind} lesson requires delivery mode {expected}")

    marker = f"session-learning:{lesson_id}"
    if status != "active":
        for instruction in (root / "AGENTS.md", root / "CLAUDE.md"):
            try:
                content = instruction.read_text(encoding="utf-8")
            except OSError:
                continue
            if marker in content:
                errors.append(f"{label}: inactive lesson remains projected with marker {marker}")
                break
    if mode == "dynamic":
        if host is not None or path_value is not None or enforcement_target is not None:
            errors.append(f"{label}: dynamic delivery must not set host, path, or enforcement_target")
        if authority == "local":
            if instruction_path is not None:
                errors.append(f"{label}: local dynamic delivery must not set instruction_path")
        else:
            errors.extend(_validate_relative_path(root, instruction_path, f"{label}: delivery.instruction_path"))
        if authority == "project" and isinstance(instruction_path, str) and not errors:
            pointer = root / instruction_path
            try:
                content = pointer.read_text(encoding="utf-8")
            except OSError:
                errors.append(f"{label}: dynamic index pointer is missing at {instruction_path}")
            else:
                if "session-learning:index" not in content:
                    errors.append(f"{label}: dynamic index pointer must contain session-learning:index")
    elif mode in {"static", "workflow"}:
        if host not in {"codex", "claude"}:
            errors.append(f"{label}: {mode} delivery requires a codex or claude host")
        errors.extend(_validate_relative_path(root, path_value, f"{label}: delivery.path"))
        if instruction_path is not None or enforcement_target is not None:
            errors.append(f"{label}: {mode} delivery has incompatible fields")
        if isinstance(path_value, str):
            normalized_path = _normalized_relative(path_value)
            if mode == "static":
                expected_name = "AGENTS.md" if host == "codex" else "CLAUDE.md"
                if Path(path_value).name != expected_name:
                    errors.append(f"{label}: {host} static delivery must target {expected_name}")
            else:
                expected_prefix = ".agents/skills/" if host == "codex" else ".claude/skills/"
                if not normalized_path.startswith(expected_prefix) or not normalized_path.endswith("/SKILL.md"):
                    errors.append(
                        f"{label}: {host} workflow delivery must use {expected_prefix}<name>/SKILL.md"
                    )
            projection = root / path_value
            if status == "active":
                try:
                    content = projection.read_text(encoding="utf-8")
                except OSError:
                    errors.append(f"{label}: active projection is missing at {path_value}")
                else:
                    if marker not in content:
                        errors.append(f"{label}: active projection is missing projection marker {marker}")
                    if mode == "workflow" and not _has_skill_frontmatter(content):
                        errors.append(f"{label}: workflow projection lacks valid SKILL.md frontmatter")
            elif projection.exists() and marker in projection.read_text(encoding="utf-8"):
                errors.append(f"{label}: inactive lesson remains projected with marker {marker}")
    elif mode == "automation":
        if any(item is not None for item in (host, path_value, instruction_path)):
            errors.append(f"{label}: automation delivery only accepts enforcement_target")
        errors.extend(
            _validate_relative_path(root, enforcement_target, f"{label}: delivery.enforcement_target")
        )
        if isinstance(enforcement_target, str) and not (root / enforcement_target).exists():
            errors.append(f"{label}: automation target is missing at {enforcement_target}")
    elif mode == "none":
        if any(item is not None for item in (host, path_value, instruction_path, enforcement_target)):
            errors.append(f"{label}: none delivery fields must be null")
    return errors


def _validate_current_lesson_record(
    record: dict[str, Any], path: Path, root: Path
) -> list[str]:
    label = str(path)
    errors = _require_fields(
        record,
        {
            "schema_version",
            "version",
            "record_type",
            "id",
            "authority",
            "equivalence_key",
            "conflict_targets",
            "conflict_history",
            "title",
            "statement",
            "kind",
            "status",
            "scope",
            "triggers",
            "anti_pattern",
            "safe_path",
            "exceptions",
            "provenance",
            "relationships",
            "usage",
            "timestamps",
        },
        label,
    )
    errors.extend(_validate_id(record, path, label))
    lesson_schema = record.get("schema_version")
    if lesson_schema != LESSON_SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {LESSON_SCHEMA_VERSION}")
    lesson_version = record.get("version")
    if not isinstance(lesson_version, str) or not SKILL_VERSION_PATTERN.fullmatch(lesson_version):
        errors.append(f"{label}: version must be a semantic skill version")
    if "delivery" not in record:
        errors.append(f"{label}: current lesson schema requires delivery")
    if record.get("record_type") != "lesson":
        errors.append(f"{label}: record_type must be 'lesson'")
    if record.get("kind") not in LESSON_KINDS:
        errors.append(f"{label}: unsupported kind {record.get('kind')!r}")
    if record.get("status") not in LESSON_STATUSES:
        errors.append(f"{label}: unsupported status {record.get('status')!r}")
    authority = record.get("authority")
    if authority not in AUTHORITIES:
        errors.append(f"{label}: authority must be project or local")
    equivalence_key = record.get("equivalence_key")
    if equivalence_key is not None and (
        not isinstance(equivalence_key, str)
        or not ID_PATTERN.fullmatch(equivalence_key)
        or equivalence_key != equivalence_key.casefold()
    ):
        errors.append(f"{label}: equivalence_key must be null or a lowercase stable key")
    conflict_targets = record.get("conflict_targets")
    conflict_history = record.get("conflict_history")
    for field, value in (("conflict_targets", conflict_targets), ("conflict_history", conflict_history)):
        if (
            not isinstance(value, list)
            or any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in value)
            or len(value) != len(set(value))
        ):
            errors.append(f"{label}: {field} must be a unique lesson-ID list")
    if isinstance(conflict_targets, list):
        if record.get("status") == "conflicted" and not conflict_targets:
            errors.append(f"{label}: conflicted lessons require conflict_targets")
        if record.get("status") != "conflicted" and conflict_targets:
            errors.append(f"{label}: only conflicted lessons may have conflict_targets")
    if isinstance(conflict_targets, list) and isinstance(conflict_history, list):
        if not set(conflict_targets).issubset(set(conflict_history)):
            errors.append(f"{label}: conflict_history must contain every conflict target")
    for field in ("title", "statement"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")
    for field in ("triggers", "anti_pattern", "safe_path", "exceptions"):
        errors.extend(_validate_string_list(record, field, label))

    scope = record.get("scope")
    if not isinstance(scope, dict) or scope.get("type") not in {"repository", "paths", "subsystem"}:
        errors.append(f"{label}: scope.type must be repository, paths, or subsystem")
    elif not isinstance(scope.get("paths"), list) or any(
        not isinstance(item, str) or not item.strip() for item in scope.get("paths", [])
    ):
        errors.append(f"{label}: scope.paths must be a list of non-empty strings")
    elif scope.get("type") in {"paths", "subsystem"} and not scope.get("paths"):
        errors.append(f"{label}: scoped lessons require at least one path")

    provenance = record.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        errors.append(f"{label}: provenance must contain at least one evidence reference")
    else:
        for item in provenance:
            if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
                errors.append(f"{label}: each provenance item needs an evidence_id")
            if not isinstance(item, dict) or item.get("signal") not in SIGNALS:
                errors.append(f"{label}: each provenance item needs a supported signal")

    relationships = record.get("relationships")
    if not isinstance(relationships, dict):
        errors.append(f"{label}: relationships must be an object")
    else:
        for field in ("supersedes", "related"):
            value = relationships.get(field)
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors.append(f"{label}: relationships.{field} must be a list of lesson IDs")

    errors.extend(_validate_usage(record.get("usage"), label))
    timestamps = record.get("timestamps")
    if not isinstance(timestamps, dict):
        errors.append(f"{label}: timestamps must be an object")
    else:
        for field in ("created_at", "updated_at"):
            value = timestamps.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: timestamps.{field} must be a non-empty string")

    errors.extend(
        _validate_delivery(
            root,
            record.get("delivery"),
            record.get("status"),
            record.get("kind"),
            record.get("id"),
            label,
            str(authority),
        )
    )
    return errors


def _validate_lesson_record(
    record: dict[str, Any], path: Path, root: Path, *, authority: str
) -> list[str]:
    """Validate current and supported legacy lessons through one normalized view."""
    try:
        normalized = upgrade_lesson_record(record, authority=authority)
    except ValueError as exc:
        return [f"{path}: {exc}"]
    return _validate_current_lesson_record(normalized, path, root)


def _validate_case_record(record: dict[str, Any], path: Path) -> list[str]:
    label = str(path)
    errors = _require_fields(
        record,
        {
            "schema_version",
            "record_type",
            "id",
            "lesson_ids",
            "situation",
            "trap",
            "expected",
            "created_at",
        },
        label,
    )
    errors.extend(_validate_id(record, path, label))
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")
    if record.get("record_type") != "case":
        errors.append(f"{label}: record_type must be 'case'")
    lesson_ids = record.get("lesson_ids")
    if not isinstance(lesson_ids, list) or not lesson_ids or any(not isinstance(item, str) for item in lesson_ids):
        errors.append(f"{label}: lesson_ids must contain at least one lesson ID")
    for field in ("situation", "trap", "expected", "created_at"):
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")
    return errors


def _scope_summary(scope: Any) -> str:
    if not isinstance(scope, dict):
        return "unknown scope"
    scope_type = str(scope.get("type", "unknown"))
    paths = scope.get("paths", [])
    if paths:
        return f"{scope_type}: {', '.join(str(item) for item in paths)}"
    return scope_type


def render_index(lessons: list[dict[str, Any]]) -> str:
    groups = {
        "Active lessons": [item for item in lessons if item.get("status") == "active"],
        "Candidates (not instructions)": [
            item for item in lessons if item.get("status") in {"candidate", "conflicted"}
        ],
        "Historical lessons": [item for item in lessons if item.get("status") in {"superseded", "retired"}],
    }
    lines = [
        "# Session Learning Index",
        "",
        "<!-- Generated by session_learning.py. Do not edit directly. -->",
        "",
        "Consult only active lessons whose scope or triggers match the current task.",
        "Candidates are not instructions and must not guide implementation.",
        "",
    ]
    for heading, records in groups.items():
        lines.extend([f"## {heading}", ""])
        if not records:
            lines.extend(["_None._", ""])
            continue
        for record in sorted(records, key=lambda item: str(item.get("id", ""))):
            record_id = str(record.get("id", ""))
            kind = str(record.get("kind", "unknown"))
            status = str(record.get("status", "unknown"))
            scope = _scope_summary(record.get("scope"))
            trigger_values = record.get("triggers")
            triggers = (
                ", ".join(" ".join(str(item).split()) for item in trigger_values)
                if isinstance(trigger_values, list)
                else ""
            )
            trigger_summary = f" · triggers: {triggers}" if triggers else ""
            statement = " ".join(str(record.get("statement", "")).split())
            lines.append(
                f"- [`{record_id}`](lessons/{record_id}.json) — **{kind}** · {status} · "
                f"`{scope}`{trigger_summary} — {statement}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_retrieval_catalog(lessons: list[dict[str, Any]]) -> bytes:
    active: list[dict[str, Any]] = []
    for record in sorted(lessons, key=lambda item: str(item.get("id", ""))):
        delivery = record.get("delivery")
        if (
            record.get("status") != "active"
            or not isinstance(delivery, dict)
            or delivery.get("mode") not in {"dynamic", "static"}
        ):
            continue
        active.append(
            {
                "id": record.get("id"),
                "authority": record.get("authority"),
                "title": record.get("title"),
                "statement": record.get("statement"),
                "scope": record.get("scope"),
                "triggers": record.get("triggers"),
                "safe_path": record.get("safe_path"),
                "exceptions": record.get("exceptions"),
                "equivalence_key": record.get("equivalence_key"),
                "delivery": delivery,
            }
        )
    if len(active) > MAX_RETRIEVAL_ENTRIES:
        raise ValueError(f"retrieval catalog exceeds {MAX_RETRIEVAL_ENTRIES} entries")
    encoded = _json_bytes(
        {"schema_version": RETRIEVAL_SCHEMA_VERSION, "lessons": active}
    )
    if len(encoded) > MAX_RETRIEVAL_BYTES:
        raise ValueError(f"retrieval catalog exceeds {MAX_RETRIEVAL_BYTES} bytes")
    return encoded


def _derived_changes(
    store: Path, lessons: list[dict[str, Any]], *, authority: str
) -> dict[Path, bytes | None]:
    index_path = store / "index.md"
    catalog_path = store / "retrieval.json"
    if not lessons:
        changes: dict[Path, bytes | None] = {}
        if index_path.exists():
            changes[index_path] = None
        if catalog_path.exists():
            changes[catalog_path] = None
        return changes
    compatible = [
        upgrade_lesson_record(_public_record(item), authority=authority)
        for item in lessons
    ]
    return {
        index_path: render_index(compatible).encode("utf-8"),
        catalog_path: render_retrieval_catalog(compatible),
    }


def rebuild_index(
    root: str | os.PathLike[str],
    *,
    authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
) -> Path:
    root_path = Path(root).resolve()
    store = store_path(root_path, authority=authority, home_dir=home_dir)
    confinement = root_path if authority == "project" else store
    with writer_lock(root_path, authority=authority):
        recover_transactions(confinement, transaction_store=store)
        lessons, load_errors = _load_records(store, "lessons")
        if load_errors:
            raise ValueError("; ".join(load_errors))
        if not lessons:
            raise ValueError("cannot rebuild index: no lesson records exist")
        changes = _derived_changes(
            store, [_public_record(item) for item in lessons], authority=authority
        )
        apply_file_transaction(
            confinement,
            changes,
            transaction_store=store,
        )
    return store / "index.md"


def validate_store(
    root: str | os.PathLike[str],
    *,
    authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
    _preloaded: tuple[
        list[dict[str, Any]],
        list[str],
        list[dict[str, Any]],
        list[str],
        list[dict[str, Any]],
        list[str],
    ] | None = None,
) -> list[str]:
    root_path = Path(root).resolve()
    if authority == "both":
        return sorted(
            set(
                error
                for item in ("project", "local")
                for error in validate_store(
                    root_path, authority=item, home_dir=home_dir
                )
            )
        )
    store = store_path(root_path, authority=authority, home_dir=home_dir)
    if not store.exists():
        return []

    if _preloaded is None:
        lessons, lesson_load_errors = _load_records(store, "lessons")
        evidence_records, evidence_load_errors = _load_records(store, "evidence")
        cases, case_load_errors = _load_records(store, "cases")
    else:
        (
            lessons,
            lesson_load_errors,
            evidence_records,
            evidence_load_errors,
            cases,
            case_load_errors,
        ) = _preloaded
    errors = lesson_load_errors + evidence_load_errors + case_load_errors

    for item in evidence_records:
        errors.extend(
            _validate_evidence_record(
                item,
                Path(item["_path"]),
                project_root=root_path,
                home_dir=(
                    Path(home_dir).expanduser().resolve()
                    if home_dir is not None
                    else Path.home()
                ),
            )
        )
    normalized_lessons: list[dict[str, Any]] = []
    for item in lessons:
        path = Path(item["_path"])
        try:
            normalized = upgrade_lesson_record(item, authority=authority)
        except ValueError as exc:
            errors.append(f"{path}: {exc}")
            continue
        normalized["_path"] = item["_path"]
        errors.extend(_validate_current_lesson_record(normalized, path, root_path))
        normalized_lessons.append(normalized)
    lessons = normalized_lessons
    for item in cases:
        errors.extend(_validate_case_record(item, Path(item["_path"])))

    lesson_ids = {item.get("id") for item in lessons if isinstance(item.get("id"), str)}
    lessons_by_id = {
        str(item["id"]): item for item in lessons if isinstance(item.get("id"), str)
    }
    evidence_ids = {item.get("id") for item in evidence_records if isinstance(item.get("id"), str)}
    evidence_by_id = {
        str(item["id"]): item
        for item in evidence_records
        if isinstance(item.get("id"), str)
    }
    for item in lessons:
        if item.get("authority") != authority:
            errors.append(f"{item.get('id', '<unknown>')}: authority does not match {authority} store")
    for item in evidence_records:
        if item.get("authority") != authority:
            errors.append(f"{item.get('id', '<unknown>')}: authority does not match {authority} store")
    seen_ids: Counter[str] = Counter(
        str(item.get("id"))
        for item in lessons + evidence_records + cases
        if isinstance(item.get("id"), str)
    )
    for record_id, count in seen_ids.items():
        if count > 1:
            errors.append(f"duplicate record id: {record_id}")

    for item in lessons:
        lesson_id = item.get("id", "<unknown>")
        for provenance in item.get("provenance", []) if isinstance(item.get("provenance"), list) else []:
            if isinstance(provenance, dict):
                evidence_id = provenance.get("evidence_id")
                if isinstance(evidence_id, str) and evidence_id not in evidence_ids:
                    errors.append(f"{lesson_id}: missing evidence {evidence_id}")
                elif isinstance(evidence_id, str):
                    evidence_record = evidence_by_id[evidence_id]
                    if evidence_record.get("authority") != item.get("authority"):
                        errors.append(
                            f"{lesson_id}: provenance crosses storage authorities: {evidence_id}"
                        )
                    if provenance.get("signal") != evidence_record.get("signal"):
                        errors.append(
                            f"{lesson_id}: provenance signal does not match evidence {evidence_id}"
                        )
        relationships = item.get("relationships")
        if isinstance(relationships, dict):
            for field in ("supersedes", "related"):
                for related_id in relationships.get(field, []) if isinstance(relationships.get(field), list) else []:
                    if related_id not in lesson_ids:
                        errors.append(f"{lesson_id}: relationships.{field} references missing lesson {related_id}")
            supersedes = relationships.get("supersedes")
            if isinstance(supersedes, list) and supersedes:
                if item.get("status") != "active":
                    errors.append(f"{lesson_id}: only an active replacement may supersede lessons")
                for target_id in supersedes:
                    target = lessons_by_id.get(str(target_id))
                    if target is not None and target.get("status") != "superseded":
                        errors.append(
                            f"{lesson_id}: supersedes target must have status 'superseded': {target_id}"
                        )
        for field in ("conflict_targets", "conflict_history"):
            for target_id in item.get(field, []) if isinstance(item.get(field), list) else []:
                target = lessons_by_id.get(str(target_id))
                if target is None:
                    errors.append(f"{lesson_id}: {field} references missing lesson {target_id}")
                elif target.get("authority") != item.get("authority"):
                    errors.append(f"{lesson_id}: {field} crosses storage authorities")

    active_equivalence: Counter[str] = Counter(
        str(item.get("equivalence_key"))
        for item in lessons
        if item.get("status") == "active" and item.get("equivalence_key") is not None
    )
    for key, count in active_equivalence.items():
        if count > 1:
            errors.append(f"duplicate active equivalence_key in {authority} authority: {key}")
    source_fingerprints: Counter[str] = Counter(
        str(item.get("source", {}).get("source_fingerprint"))
        for item in evidence_records
        if item.get("signal") == "recovery_pair" and isinstance(item.get("source"), dict)
    )
    for fingerprint, count in source_fingerprints.items():
        if count > 1:
            errors.append(f"duplicate recovery source_fingerprint: {fingerprint}")

    active_supersession_targets = {
        str(target_id)
        for item in lessons
        if item.get("status") == "active" and isinstance(item.get("relationships"), dict)
        for target_id in item["relationships"].get("supersedes", [])
        if isinstance(target_id, str)
    }
    for item in lessons:
        if item.get("status") == "superseded" and item.get("id") not in active_supersession_targets:
            errors.append(
                f"{item.get('id', '<unknown>')}: superseded lesson has no active replacement"
            )

    for item in cases:
        case_id = item.get("id", "<unknown>")
        for lesson_id in item.get("lesson_ids", []) if isinstance(item.get("lesson_ids"), list) else []:
            if lesson_id not in lesson_ids:
                errors.append(f"{case_id}: references missing lesson {lesson_id}")

    if lessons:
        expected = render_index(lessons)
        index_path = store / "index.md"
        try:
            actual = index_path.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"{index_path}: index.md is missing")
        else:
            if actual != expected:
                errors.append(f"{index_path}: index.md is stale; run rebuild-index")
        catalog_path = store / "retrieval.json"
        try:
            if catalog_path.stat().st_size > MAX_RETRIEVAL_BYTES:
                raise ValueError("catalog is oversized")
            catalog_actual = catalog_path.read_bytes()
            catalog_expected = render_retrieval_catalog(
                [_public_record(item) for item in lessons]
            )
        except (OSError, ValueError) as exc:
            errors.append(f"{catalog_path}: retrieval catalog is missing or invalid: {exc}")
        else:
            if catalog_actual != catalog_expected:
                errors.append(f"{catalog_path}: retrieval catalog is stale; run rebuild-index")
    elif (store / "index.md").exists():
        errors.append(f"{store / 'index.md'}: index exists without lesson records")
    return sorted(set(errors))


def audit_store(
    root: str | os.PathLike[str], *, authority: str = "project",
    home_dir: str | os.PathLike[str] | None = None,
    data_dir: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    if authority == "both":
        reports = {
            item: audit_store(root, authority=item, home_dir=home_dir, data_dir=data_dir)
            for item in ("project", "local")
        }
        hook_errors = reports["project"]["hook_errors"]
        hook_error_load_errors = reports["project"]["hook_error_load_errors"]
        return {
            "authority": "both",
            "authorities": reports,
            "skill_version": SKILL_VERSION,
            "lesson_schema_version": LESSON_SCHEMA_VERSION,
            "migration_available": any(
                report["migration_candidates"] for report in reports.values()
            ),
            "migration_candidates": sorted(
                (
                    candidate
                    for report in reports.values()
                    for candidate in report["migration_candidates"]
                ),
                key=lambda item: (str(item.get("authority")), str(item.get("id"))),
            ),
            "hook_errors": hook_errors,
            "hook_error_load_errors": hook_error_load_errors,
            "validation_errors": sorted(
                error for report in reports.values() for error in report["validation_errors"]
            ),
            "load_errors": sorted(
                error for report in reports.values() for error in report["load_errors"]
            ),
        }
    store = store_path(root, authority=authority, home_dir=home_dir)
    lessons, lesson_errors = _load_records(store, "lessons")
    evidence_records, evidence_errors = _load_records(store, "evidence")
    cases, case_errors = _load_records(store, "cases")
    status_counts = Counter(str(item.get("status", "invalid")) for item in lessons)
    kind_counts = Counter(str(item.get("kind", "invalid")) for item in lessons)
    referenced_evidence = {
        provenance.get("evidence_id")
        for lesson_item in lessons
        for provenance in lesson_item.get("provenance", [])
        if isinstance(provenance, dict) and isinstance(provenance.get("evidence_id"), str)
    }
    evidence_ids = {
        item.get("id") for item in evidence_records if isinstance(item.get("id"), str)
    }
    migration_candidates = sorted(
        [
            {
                "authority": authority,
                "id": str(item.get("id", Path(str(item.get("_path", "unknown"))).stem)),
                "schema_version": item.get("schema_version"),
                "version": (
                    item.get("version")
                    if isinstance(item.get("version"), str)
                    else "legacy"
                ),
            }
            for item in lessons
            if lesson_needs_migration(item)
        ],
        key=lambda item: str(item["id"]),
    )
    home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
    hook_errors, hook_error_load_errors = _load_hook_error_reports(
        Path(root).expanduser().resolve(), home=home, data_dir=data_dir
    )
    violations = 0
    repeat_corrections = 0
    for item in lessons:
        item_usage = item.get("usage")
        if isinstance(item_usage, dict):
            if isinstance(item_usage.get("violations"), int):
                violations += item_usage["violations"]
            if isinstance(item_usage.get("repeat_corrections"), int):
                repeat_corrections += item_usage["repeat_corrections"]
    return {
        "authority": authority,
        "skill_version": SKILL_VERSION,
        "lesson_schema_version": LESSON_SCHEMA_VERSION,
        "total_lessons": len(lessons),
        "status_counts": dict(sorted(status_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
        "violations": violations,
        "repeat_corrections": repeat_corrections,
        "unresolved_conflicts": sorted(
            str(item.get("id")) for item in lessons if item.get("status") == "conflicted"
        ),
        "orphan_evidence": sorted(str(item) for item in evidence_ids - referenced_evidence),
        "migration_available": bool(migration_candidates),
        "migration_candidates": migration_candidates,
        "hook_errors": hook_errors,
        "hook_error_load_errors": hook_error_load_errors,
        "load_errors": sorted(lesson_errors + evidence_errors + case_errors),
        "validation_errors": validate_store(
            root,
            authority=authority,
            home_dir=home_dir,
            _preloaded=(
                lessons,
                lesson_errors,
                evidence_records,
                evidence_errors,
                cases,
                case_errors,
            ),
        ),
    }


def _load_history_module() -> Any:
    name = "session_learning_history_runtime"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).with_name("session_learning_history.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load history analyzer: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _history_classifications(
    root: Path,
    candidates: Iterable[Any],
    *,
    home_dir: str | os.PathLike[str] | None,
) -> tuple[dict[str, str], list[str], str]:
    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    for _, store in authority_stores(root, "both", home_dir=home_dir):
        records, load_errors = _load_records(store, "evidence")
        evidence.extend(_public_record(item) for item in records)
        errors.extend(load_errors)
    classifications: dict[str, str] = {}
    for candidate in candidates:
        state = "new"
        for record in evidence:
            source = record.get("source")
            if not isinstance(source, dict) or record.get("session_id") != candidate.session_id:
                continue
            if source.get("source_fingerprint") == candidate.source_fingerprint:
                if record.get("authority") != candidate.authority:
                    state = "authority_reconciliation_required"
                else:
                    state = (
                        "unchanged"
                        if source.get("content_fingerprint") == candidate.content_fingerprint
                        else "reinterpretation_required"
                    )
                break
            if (
                source.get("failure_event_id") in {candidate.failure_id, candidate.verification_id}
                or source.get("verification_event_id") in {candidate.failure_id, candidate.verification_id}
            ):
                state = "source_reconciliation_required"
        classifications[candidate.source_fingerprint] = state
    fingerprint_records = [
        {
            "id": item.get("id"),
            "authority": item.get("authority"),
            "session_id": item.get("session_id"),
            "source": item.get("source"),
        }
        for item in sorted(evidence, key=lambda value: str(value.get("id", "")))
    ]
    evidence_fingerprint = hashlib.sha256(
        _json_bytes({"records": fingerprint_records, "errors": sorted(errors)})
    ).hexdigest()
    return classifications, errors, evidence_fingerprint


def mine_history(
    root: str | os.PathLike[str],
    *,
    host: str = "codex",
    home_dir: str | os.PathLike[str] | None = None,
    since: str | None = None,
    session_id: str | None = None,
    page: int = 1,
    detail_id: str | None = None,
    report_filter: str = "actionable",
    expect_scan: str | None = None,
) -> tuple[dict[str, Any], int]:
    if host != "codex":
        raise ValueError("only the Codex history scanner is currently supported")
    history = _load_history_module()
    scan = history.CodexSessionScanner().scan(
        root, home_dir=home_dir, since=since, session_id=session_id
    )
    classifications, evidence_errors, evidence_fingerprint = _history_classifications(
        Path(root).resolve(), scan.candidates, home_dir=home_dir
    )
    combined_scan_fingerprint = hashlib.sha256(
        f"{scan.scan_fingerprint}\0{evidence_fingerprint}".encode("utf-8")
    ).hexdigest()
    scan = history.HistoryScan(
        scan.status, scan.candidates, scan.diagnostics, scan.selected_sessions,
        scan.scanned_sessions, scan.skipped_sessions, scan.failed_sessions,
        scan.discovery_complete, combined_scan_fingerprint, scan.rejection_counts,
    )
    if evidence_errors:
        scan = history.HistoryScan(
            "degraded", scan.candidates,
            (*scan.diagnostics, history.ScanDiagnostic(
                "evidence_lookup_incomplete", "existing evidence could not be read completely"
            )),
            scan.selected_sessions, scan.scanned_sessions, scan.skipped_sessions,
            scan.failed_sessions, False, scan.scan_fingerprint, scan.rejection_counts,
        )
    if expect_scan is not None and expect_scan != scan.scan_fingerprint:
        raise ValueError("scan fingerprint changed; rerun from page 1")
    report = history.render_scan_report(
        scan, page=page, detail_id=detail_id, report_filter=report_filter,
        classifications=classifications,
    )
    return report, {"complete": 0, "failed": 1, "degraded": 2}[scan.status]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Rank stored lessons for a query")
    search.add_argument("query", nargs="+", help="Search terms")
    search.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    search.add_argument("--json", action="store_true", help="Emit JSON")
    search.add_argument("--all", action="store_true", help="Include zero-score lessons")
    search.add_argument("--authority", choices=("project", "local", "both"), default="project")
    search.add_argument("--home-dir")

    validate = subparsers.add_parser("validate", help="Validate the learning store")
    validate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    validate.add_argument("--authority", choices=("project", "local", "both"), default="project")
    validate.add_argument("--home-dir")

    rebuild = subparsers.add_parser("rebuild-index", help="Regenerate index.md")
    rebuild.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    rebuild.add_argument("--authority", choices=("project", "local"), default="project")
    rebuild.add_argument("--home-dir")

    audit = subparsers.add_parser("audit", help="Summarize learning-store health")
    audit.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    audit.add_argument("--json", action="store_true", help="Emit JSON")
    audit.add_argument("--authority", choices=("project", "local", "both"), default="project")
    audit.add_argument("--home-dir")
    audit.add_argument("--data-dir", help="Optional host plugin-data directory containing hook errors")

    activate = subparsers.add_parser("activate", help="Activate v2 delivery for a project")
    activate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    activate.add_argument("--host", choices=("auto", "codex", "claude", "both"), default="auto")

    delivery = subparsers.add_parser("set-delivery", help="Set dynamic or static lesson delivery")
    delivery.add_argument("lesson_id")
    delivery.add_argument("mode", choices=("dynamic", "static", "none"))
    delivery.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    delivery.add_argument("--host", choices=("codex", "claude"), default="codex")
    delivery.add_argument("--authority", choices=("project", "local"), default="project")
    delivery.add_argument("--home-dir")

    deactivate = subparsers.add_parser("deactivate", help="Retire a lesson and remove its projection")
    deactivate.add_argument("lesson_id")
    deactivate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    deactivate.add_argument("--authority", choices=("project", "local"), default="project")
    deactivate.add_argument("--home-dir")

    reactivate = subparsers.add_parser("reactivate", help="Return a retired lesson to candidate status")
    reactivate.add_argument("lesson_id")
    reactivate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    reactivate.add_argument("--authority", choices=("project", "local"), default="project")
    reactivate.add_argument("--home-dir")

    reconcile = subparsers.add_parser("reconcile-delivery", help="Report or repair delivery drift")
    reconcile.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    reconcile.add_argument("--host", choices=("codex", "claude"), required=True)
    reconcile.add_argument("--apply", action="store_true")

    manifest = subparsers.add_parser("apply-manifest", help="Apply an authoring manifest transactionally")
    manifest.add_argument("manifest")
    manifest.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    manifest.add_argument("--authority", choices=("project", "local"), default="project")
    manifest.add_argument("--home-dir")

    mine = subparsers.add_parser("mine-history", help="Dry-run recovery mining over Codex history")
    mine.add_argument("--host", choices=("codex",), default="codex")
    mine.add_argument("--root", required=True, help="Requested project root")
    mine.add_argument("--home-dir")
    mine.add_argument("--since")
    mine.add_argument("--session", dest="session_id")
    mine.add_argument("--json", action="store_true")
    mine.add_argument("--detail")
    mine.add_argument("--page", type=int, default=1)
    mine.add_argument(
        "--report-filter", choices=("actionable", "new", "reinterpretation"),
        default="actionable",
    )
    mine.add_argument("--expect-scan")

    hook = subparsers.add_parser("hook", help="Process one host hook event from stdin")
    hook.add_argument("--host", choices=("codex", "claude"), required=True)
    hook.add_argument("--data-dir", required=True)
    hook.add_argument("--home-dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "hook":
        try:
            payload = json.load(sys.stdin)
            result = handle_hook_event(
                payload,
                host=args.host,
                data_dir=args.data_dir,
                home_dir=args.home_dir,
            )
        except Exception:
            # Hook failures are deliberately silent and fail open. Maintainer
            # commands below retain their normal nonzero error behavior.
            return 0
        if result:
            print(json.dumps(result, separators=(",", ":")))
        return 0
    root = resolve_project_root(args.root)
    if args.command == "search":
        try:
            results = search_lessons(
                root, " ".join(args.query), include_all=args.all,
                authority=args.authority, home_dir=args.home_dir,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(results, indent=2, sort_keys=True))
        else:
            for result in results:
                print(f"{result['score']:>3}  {result.get('id', '<unknown>')}  {result.get('statement', '')}")
        return 0
    if args.command == "validate":
        errors = validate_store(root, authority=args.authority, home_dir=args.home_dir)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Valid session-learning authority: {args.authority}")
        return 0
    if args.command == "rebuild-index":
        try:
            target = rebuild_index(root, authority=args.authority, home_dir=args.home_dir)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(target)
        return 0
    if args.command == "audit":
        audit = audit_store(
            root,
            authority=args.authority,
            home_dir=args.home_dir,
            data_dir=args.data_dir,
        )
        if args.json:
            print(json.dumps(audit, indent=2, sort_keys=True))
        else:
            if args.authority == "both":
                for name, report in audit["authorities"].items():
                    print(f"{name}: lessons={report['total_lessons']} statuses={report['status_counts']}")
            else:
                print(f"Lessons: {audit['total_lessons']}")
                print(f"Statuses: {audit['status_counts']}")
                print(f"Kinds: {audit['kind_counts']}")
                print(f"Violations: {audit['violations']}")
                print(f"Repeat corrections: {audit['repeat_corrections']}")
                print(f"Conflicts: {audit['unresolved_conflicts']}")
                print(f"Orphan evidence: {audit['orphan_evidence']}")
            if audit["validation_errors"]:
                print(f"Validation errors: {len(audit['validation_errors'])}")
            if audit.get("migration_candidates"):
                print(f"Migration candidates: {len(audit['migration_candidates'])}")
            if audit.get("hook_errors"):
                occurrences = sum(
                    int(item.get("occurrences", 0)) for item in audit["hook_errors"]
                )
                print(
                    f"Hook errors: {len(audit['hook_errors'])} distinct, "
                    f"{occurrences} occurrences"
                )
                for item in audit["hook_errors"]:
                    suffix = f" file={item['file']}" if item.get("file") else ""
                    print(
                        f"- {item.get('category')} {item.get('exception_type')} "
                        f"during {item.get('hook_event')} ({item.get('occurrences')} occurrences)"
                        f"{suffix}"
                    )
        return 1 if (
            audit["load_errors"]
            or audit["validation_errors"]
            or audit.get("hook_error_load_errors")
        ) else 0
    if args.command == "activate":
        print(json.dumps(activate_store(root, host=args.host), indent=2, sort_keys=True))
        return 0
    if args.command == "set-delivery":
        print(
            json.dumps(
                set_delivery(
                    root, args.lesson_id, args.mode, host=args.host,
                    authority=args.authority, home_dir=args.home_dir,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "deactivate":
        print(json.dumps(deactivate_lesson(
            root, args.lesson_id, authority=args.authority, home_dir=args.home_dir
        ), indent=2, sort_keys=True))
        return 0
    if args.command == "reactivate":
        print(json.dumps(reactivate_lesson(
            root, args.lesson_id, authority=args.authority, home_dir=args.home_dir
        ), indent=2, sort_keys=True))
        return 0
    if args.command == "reconcile-delivery":
        print(
            json.dumps(
                reconcile_delivery(root, host=args.host, apply=args.apply),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "apply-manifest":
        try:
            manifest_value = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            result = apply_manifest(
                root, manifest_value, authority=args.authority, home_dir=args.home_dir
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.command == "mine-history":
        try:
            report, exit_code = mine_history(
                root, host=args.host, home_dir=args.home_dir, since=args.since,
                session_id=args.session_id, page=args.page, detail_id=args.detail,
                report_filter=args.report_filter, expect_scan=args.expect_scan,
            )
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        elif args.detail:
            candidate = report["candidate"]
            delta = candidate["behavior_delta"]
            print(f"Scan: {report['status']} ({report['counts']['scanned_sessions']} sessions scanned)")
            print(
                f"{candidate['id']} [{candidate['authority']}] "
                f"{candidate['classification']}"
            )
            print(f"Behavior: {delta['before']} -> {delta['after']}")
            print(f"Contrast: {candidate['contrast']}")
            print(f"Source: {candidate['source']}")
        else:
            print(f"Scan: {report['status']} ({report['counts']['actionable']} actionable)")
            print(
                "Sessions: "
                f"{report['counts']['scanned_sessions']} scanned, "
                f"{report['counts']['skipped_sessions']} skipped, "
                f"{report['counts']['failed_sessions']} failed"
            )
            for candidate in report.get("candidates", []):
                delta = candidate["behavior_delta"]
                print(f"{candidate['id']} [{candidate['authority']}] {delta['before']} -> {delta['after']}")
            for diagnostic in report.get("diagnostics", []):
                print(f"Diagnostic: {diagnostic['code']} - {diagnostic['message']}")
            if report.get("pagination", {}).get("next_page"):
                print(f"Next page: {report['pagination']['next_page']}")
        return exit_code
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
