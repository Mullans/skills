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
from datetime import datetime, timezone
import fnmatch
import hashlib
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
LESSON_SCHEMA_VERSION = 2
STORE_RELATIVE = Path(".agents") / "learning"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

LESSON_KINDS = {"guardrail", "workflow", "project_knowledge", "preference", "invariant"}
LESSON_STATUSES = {"candidate", "active", "conflicted", "superseded", "retired"}
DESTINATION_TYPES = {"instruction", "index", "skill", "automation", "evidence_only", "none"}
DELIVERY_MODES = {"dynamic", "static", "workflow", "automation", "none"}
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
}
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


def store_path(root: str | os.PathLike[str]) -> Path:
    return Path(root).resolve() / STORE_RELATIVE


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
    root: str | os.PathLike[str], query: str, *, include_all: bool = False
) -> list[dict[str, Any]]:
    """Return lessons ranked by trigger/scope, statement, then general metadata."""
    store = store_path(root)
    lessons, load_errors = _load_records(store, "lessons")
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
    results.sort(key=lambda item: (-int(item["score"]), str(item.get("id", ""))))
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


def _validate_evidence_record(record: dict[str, Any], path: Path) -> list[str]:
    label = str(path)
    errors = _require_fields(
        record,
        {
            "schema_version",
            "record_type",
            "id",
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
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")
    if record.get("record_type") != "evidence":
        errors.append(f"{label}: record_type must be 'evidence'")
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
) -> list[Path]:
    """Atomically replace a set of project files and roll back on failure.

    Individual replacements are atomic. A short-lived journal and snapshots make
    the multi-file operation recoverable when validation or a later write fails.
    """
    root_path = Path(root).resolve()
    recover_transactions(root_path)
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

    transaction_root = store_path(root_path) / ".transactions"
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


def recover_transactions(root: str | os.PathLike[str]) -> int:
    """Roll back transactions whose journal survived an interrupted process."""
    root_path = Path(root).resolve()
    transaction_root = store_path(root_path) / ".transactions"
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


def _delivery_from_v1(record: dict[str, Any], host: str) -> dict[str, Any]:
    destination = record.get("destination")
    if not isinstance(destination, dict) or record.get("status") != "active":
        return {
            "mode": "none",
            "host": None,
            "path": None,
            "instruction_path": None,
            "enforcement_target": None,
        }
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
        if not isinstance(instruction_path, str):
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
    return {
        "mode": "none",
        "host": None,
        "path": None,
        "instruction_path": None,
        "enforcement_target": None,
    }


def _all_lesson_records_with_replacements(
    store: Path, replacements: dict[Path, dict[str, Any]]
) -> list[dict[str, Any]]:
    lessons, errors = _load_records(store, "lessons")
    if errors:
        raise ValueError("; ".join(errors))
    return [replacements.get(Path(item["_path"]), _public_record(item)) for item in lessons]


def migrate_store(root: str | os.PathLike[str], *, host: str = "codex") -> dict[str, Any]:
    if host not in {"codex", "claude", "both"}:
        raise ValueError("host must be codex, claude, or both")
    root_path = Path(root).resolve()
    store = store_path(root_path)
    lessons, errors = _load_records(store, "lessons")
    if errors:
        raise ValueError("; ".join(errors))
    if not lessons:
        return {"changed": False, "files": []}
    effective_host = "claude" if host == "claude" else "codex"
    replacements: dict[Path, dict[str, Any]] = {}
    changes: dict[Path, bytes | None] = {}
    instruction_updates: dict[Path, str] = {}

    for item in lessons:
        path = Path(item["_path"])
        if item.get("schema_version") == LESSON_SCHEMA_VERSION and "delivery" in item:
            continue
        record = _public_record(item)
        old_destination = record.pop("destination", None)
        record["schema_version"] = LESSON_SCHEMA_VERSION
        record["delivery"] = _delivery_from_v1({**record, "destination": old_destination}, effective_host)
        replacements[path] = record
        changes[path] = _json_bytes(record)
        if isinstance(old_destination, dict) and old_destination.get("type") == "instruction":
            old_path = old_destination.get("path")
            if isinstance(old_path, str):
                target = root_path / old_path
                content = instruction_updates.get(
                    target, target.read_text(encoding="utf-8") if target.exists() else ""
                )
                if record["delivery"]["mode"] == "dynamic":
                    content = _remove_marker_block(content, f"session-learning:{record['id']}")
                instruction_updates[target] = content

    all_lessons = _all_lesson_records_with_replacements(store, replacements)
    active_dynamic = [
        item
        for item in all_lessons
        if item.get("status") == "active"
        and isinstance(item.get("delivery"), dict)
        and item["delivery"].get("mode") == "dynamic"
    ]
    if active_dynamic:
        pointer_path_value = active_dynamic[0]["delivery"].get("instruction_path")
        pointer_path = root_path / str(pointer_path_value or ("CLAUDE.md" if effective_host == "claude" else "AGENTS.md"))
        pointer_content = instruction_updates.get(
            pointer_path,
            pointer_path.read_text(encoding="utf-8") if pointer_path.exists() else "",
        )
        instruction_updates[pointer_path] = _ensure_pointer(pointer_content)
    for target, content in instruction_updates.items():
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != content:
            changes[target] = content.encode("utf-8")
    if replacements:
        changes[store / "index.md"] = render_index(all_lessons).encode("utf-8")
    if not changes:
        return {"changed": False, "files": []}
    written = apply_file_transaction(
        root_path, changes, validator=lambda: validate_store(root_path)
    )
    return {
        "changed": True,
        "files": [path.relative_to(root_path).as_posix() for path in written],
    }


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
    result = migrate_store(root, host=resolved_host)
    root_path = Path(root).resolve()
    extra: dict[Path, bytes | None] = {}
    if resolved_host == "both" and _needs_claude_bridge(root_path):
        extra.update(_ensure_claude_bridge(root_path))
    if extra:
        written = apply_file_transaction(root_path, extra, validator=lambda: validate_store(root_path))
        result = {
            "changed": True,
            "files": sorted(
                set(result.get("files", []))
                | {path.relative_to(root_path).as_posix() for path in written}
            ),
        }
    return result


def _load_lesson_by_id(root: Path, lesson_id: str) -> tuple[Path, dict[str, Any]]:
    path = store_path(root) / "lessons" / f"{lesson_id}.json"
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


def deactivate_lesson(root: str | os.PathLike[str], lesson_id: str) -> dict[str, Any]:
    root_path = Path(root).resolve()
    migrate_store(root_path)
    lesson_path, old_record = _load_lesson_by_id(root_path, lesson_id)
    record = dict(old_record)
    record["status"] = "retired"
    record["delivery"] = {
        "mode": "none",
        "host": None,
        "path": None,
        "instruction_path": None,
        "enforcement_target": None,
    }
    changes = _changes_for_lesson_update(root_path, lesson_path, record, old_record)
    written = apply_file_transaction(
        root_path, changes, validator=lambda: validate_store(root_path)
    )
    return {"lesson_id": lesson_id, "status": "retired", "files": [str(path) for path in written]}


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
    root: str | os.PathLike[str], lesson_id: str, mode: str, *, host: str = "codex"
) -> dict[str, Any]:
    if mode not in {"dynamic", "static"}:
        raise ValueError("set-delivery mode must be dynamic or static")
    if host not in {"codex", "claude"}:
        raise ValueError("host must be codex or claude")
    root_path = Path(root).resolve()
    migrate_store(root_path, host=host)
    lesson_path, old_record = _load_lesson_by_id(root_path, lesson_id)
    if old_record.get("status") != "active":
        raise ValueError("only active lessons can change delivery mode")
    record = dict(old_record)
    projection_changes: dict[Path, bytes | None] = {}
    if mode == "dynamic":
        instruction_path = "CLAUDE.md" if host == "claude" else "AGENTS.md"
        record["delivery"] = {
            "mode": "dynamic",
            "host": None,
            "path": None,
            "instruction_path": instruction_path,
            "enforcement_target": None,
        }
        pointer = root_path / instruction_path
        content = pointer.read_text(encoding="utf-8") if pointer.exists() else ""
        old_delivery = old_record.get("delivery")
        if (
            isinstance(old_delivery, dict)
            and old_delivery.get("mode") == "static"
            and old_delivery.get("path") == instruction_path
        ):
            content = _remove_marker_block(content, f"session-learning:{lesson_id}")
        projection_changes[pointer] = _ensure_pointer(content).encode("utf-8")
    else:
        projection_path = "CLAUDE.md" if host == "claude" else "AGENTS.md"
        record["delivery"] = {
            "mode": "static",
            "host": host,
            "path": projection_path,
            "instruction_path": None,
            "enforcement_target": None,
        }
        target = root_path / projection_path
        content = target.read_text(encoding="utf-8") if target.exists() else ""
        marker = f"session-learning:{lesson_id}"
        if marker not in content:
            base = content.rstrip()
            block = f"<!-- {marker} -->\n- {' '.join(str(record['statement']).split())}\n"
            content = (base + "\n\n" if base else "") + block
        projection_changes[target] = content.encode("utf-8")
    changes = _changes_for_lesson_update(root_path, lesson_path, record, old_record)
    changes.update(projection_changes)
    written = apply_file_transaction(
        root_path, changes, validator=lambda: validate_store(root_path)
    )
    return {"lesson_id": lesson_id, "mode": mode, "files": [str(path) for path in written]}


def reactivate_lesson(root: str | os.PathLike[str], lesson_id: str) -> dict[str, Any]:
    """Move a retired lesson back to candidate so the retrospective can re-gate it."""
    root_path = Path(root).resolve()
    migrate_store(root_path)
    lesson_path, old_record = _load_lesson_by_id(root_path, lesson_id)
    if old_record.get("status") != "retired":
        raise ValueError("only retired lessons can be reactivated")
    record = dict(old_record)
    record["status"] = "candidate"
    record["delivery"] = {
        "mode": "none",
        "host": None,
        "path": None,
        "instruction_path": None,
        "enforcement_target": None,
    }
    changes = _changes_for_lesson_update(root_path, lesson_path, record, old_record)
    written = apply_file_transaction(
        root_path, changes, validator=lambda: validate_store(root_path)
    )
    return {"lesson_id": lesson_id, "status": "candidate", "files": [str(path) for path in written]}


def _manifest_path_allowed(relative: Path) -> bool:
    normalized = relative.as_posix()
    if relative.name in {"AGENTS.md", "CLAUDE.md"}:
        return True
    if normalized == ".agents/learning/config.json":
        return True
    if re.fullmatch(r"\.agents/learning/(lessons|evidence|cases)/[^/]+\.json", normalized):
        return True
    if re.fullmatch(r"\.(agents|claude)/skills/[^/]+/SKILL\.md", normalized):
        return True
    return False


def apply_manifest(root: str | os.PathLike[str], manifest: dict[str, Any]) -> dict[str, Any]:
    """Apply an authoring manifest through the recoverable transaction layer."""
    if not isinstance(manifest, dict) or manifest.get("manifest_schema_version") != 1:
        raise ValueError("manifest_schema_version must be 1")
    entries = manifest.get("changes")
    if not isinstance(entries, list) or not entries:
        return {"changed": False, "files": []}
    root_path = Path(root).resolve()
    changes: dict[Path, bytes | None] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("each manifest change requires a relative path")
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or not _manifest_path_allowed(relative):
            raise ValueError(f"unsupported transaction path: {entry['path']}")
        target = _within_root(root_path, root_path / relative)
        variants = [key for key in ("json", "content", "delete") if key in entry]
        if len(variants) != 1:
            raise ValueError(f"manifest change for {entry['path']} requires exactly one payload")
        if "json" in entry:
            if not isinstance(entry["json"], dict):
                raise ValueError(f"manifest JSON payload must be an object: {entry['path']}")
            changes[target] = _json_bytes(entry["json"])
        elif "content" in entry:
            if not isinstance(entry["content"], str):
                raise ValueError(f"manifest content must be text: {entry['path']}")
            changes[target] = entry["content"].encode("utf-8")
        else:
            if entry["delete"] is not True:
                raise ValueError(f"manifest delete must be true: {entry['path']}")
            changes[target] = None

    lessons, load_errors = _load_records(store_path(root_path), "lessons")
    if load_errors:
        raise ValueError("; ".join(load_errors))
    prospective: dict[Path, dict[str, Any]] = {
        Path(item["_path"]): _public_record(item) for item in lessons
    }
    for target, content in changes.items():
        if target.parent != store_path(root_path) / "lessons":
            continue
        if content is None:
            prospective.pop(target, None)
            continue
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid lesson JSON in manifest: {target}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"lesson record must be an object: {target}")
        prospective[target] = value
    index_path = store_path(root_path) / "index.md"
    if prospective:
        changes[index_path] = render_index(list(prospective.values())).encode("utf-8")
    elif index_path.exists():
        changes[index_path] = None
    written = apply_file_transaction(
        root_path, changes, validator=lambda: validate_store(root_path)
    )
    return {
        "changed": bool(written),
        "files": [path.relative_to(root_path).as_posix() for path in written],
    }


def find_learning_root(cwd: str | os.PathLike[str]) -> Path | None:
    start = Path(cwd).expanduser().resolve()
    candidates = [start, *start.parents]
    for candidate in candidates:
        if (candidate / STORE_RELATIVE / "lessons").is_dir():
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


def _state_path(data_dir: Path, root: Path, session_id: str) -> Path:
    project_hash = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:16]
    session_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return data_dir / f"state-{project_hash}-{session_hash}.json"


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


INDEX_LESSON_PATTERN = re.compile(r"^- \[`([a-z0-9][a-z0-9._-]*)`\]\(lessons/[^)]+\)")
INDEX_NOISE_TOKENS = {
    "and",
    "change",
    "for",
    "from",
    "into",
    "project",
    "run",
    "task",
    "that",
    "the",
    "this",
    "update",
    "use",
    "using",
    "when",
    "with",
}


def _index_candidate_ids(
    store: Path, *, text: str, event_paths: list[str], tool_input: Any
) -> set[str] | None:
    """Use the generated human index to avoid opening every lesson on each hook."""
    index_path = store / "index.md"
    if not index_path.is_file():
        return None
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    query = " ".join([text, *event_paths, *_string_values(tool_input)])
    query_tokens = {
        token
        for token in _tokens(query)
        if len(token) >= 2 and token not in INDEX_NOISE_TOKENS
    }
    if not query_tokens:
        return set()
    candidates: set[str] = set()
    in_active = False
    for line in lines:
        if line == "## Active lessons":
            in_active = True
            continue
        if in_active and line.startswith("## "):
            break
        if not in_active:
            continue
        match = INDEX_LESSON_PATTERN.match(line)
        if match and query_tokens & _tokens(line):
            candidates.add(match.group(1))
    return candidates


def _load_lesson_candidates(
    store: Path, candidate_ids: set[str] | None
) -> tuple[list[dict[str, Any]], list[str]]:
    if candidate_ids is None:
        return _load_records(store, "lessons")
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for lesson_id in sorted(candidate_ids):
        if not ID_PATTERN.fullmatch(lesson_id):
            continue
        path = store / "lessons" / f"{lesson_id}.json"
        if not path.is_file():
            continue
        try:
            records.append(_read_record(path))
        except ValueError as exc:
            errors.append(str(exc))
    return records, errors


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


def _claude_imports_agents(root: Path, cwd: Path, agents_path: Path) -> bool:
    current = cwd.resolve()
    for directory in [current, *current.parents]:
        try:
            directory.relative_to(root)
        except ValueError:
            break
        claude = directory / "CLAUDE.md"
        if claude.is_file():
            content = claude.read_text(encoding="utf-8")
            for match in re.finditer(r"(?m)^@(\.?\.?[/\\][^\r\n]+|[^\r\n]+)$", content):
                imported = (directory / match.group(1).strip()).resolve()
                if imported == agents_path.resolve():
                    return True
        if directory == root:
            break
    return False


def _static_visible(lesson: dict[str, Any], root: Path, cwd: Path, host: str) -> bool:
    delivery = lesson.get("delivery")
    if not isinstance(delivery, dict) or delivery.get("mode") != "static":
        return False
    path_value = delivery.get("path")
    if not isinstance(path_value, str):
        return False
    projection = root / path_value
    marker = f"session-learning:{lesson.get('id')}"
    if not projection.is_file() or marker not in projection.read_text(encoding="utf-8"):
        return False
    try:
        cwd.resolve().relative_to(projection.parent.resolve())
    except ValueError:
        return False
    if delivery.get("host") == host:
        return True
    if host == "claude" and projection.name == "AGENTS.md":
        return _claude_imports_agents(root, cwd, projection)
    return False


def _hook_context(event_name: str, lessons: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    if not lessons:
        return {}
    header = "Relevant project lessons:\n"
    parts = [header]
    for lesson in lessons:
        safe_path = lesson.get("safe_path")
        safe = "; ".join(str(item) for item in safe_path) if isinstance(safe_path, list) else ""
        line = f"- [{lesson.get('id')}] {' '.join(str(lesson.get('statement', '')).split())}"
        if safe:
            line += f" Safe path: {safe}."
        line += "\n"
        if sum(len(item) for item in parts) + len(line) > limit:
            break
        parts.append(line)
    if len(parts) == 1:
        return {}
    return {
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
    root = find_learning_root(cwd_value)
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
    home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home()
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
    candidate_ids: set[str] | None = None
    if bypass_cooldown:
        candidate_ids = set(state["relevant"])
    elif event_name in {"UserPromptSubmit", "PreToolUse"}:
        if event_name == "UserPromptSubmit":
            state["prompt_sequence"] += 1
            text = str(payload.get("prompt", ""))
        else:
            text = " ".join(_string_values(payload.get("tool_input")))
        event_paths = _relative_event_paths(root, payload.get("tool_input"))
        candidate_ids = _index_candidate_ids(
            store_path(root),
            text=text,
            event_paths=event_paths,
            tool_input=payload.get("tool_input"),
        )
    lessons, errors = _load_lesson_candidates(store_path(root), candidate_ids)
    if errors:
        return {}
    active = [
        _public_record(item)
        for item in lessons
        if item.get("status") == "active"
        and item.get("schema_version") == LESSON_SCHEMA_VERSION
        and isinstance(item.get("delivery"), dict)
        and item["delivery"].get("mode") in {"dynamic", "static"}
    ]
    by_id = {str(item.get("id")): item for item in active}

    selected: list[dict[str, Any]] = []
    if bypass_cooldown:
        selected = [by_id[item] for item in state["relevant"] if item in by_id]
    elif event_name in {"UserPromptSubmit", "PreToolUse"}:
        scored: list[tuple[int, dict[str, Any]]] = []
        cwd = Path(cwd_value)
        for lesson in active:
            if _static_visible(lesson, root, cwd, host):
                continue
            score = _lesson_score(
                lesson, text=text, event_paths=event_paths, tool_input=payload.get("tool_input")
            )
            if score < 25:
                continue
            last = state["delivered"].get(str(lesson.get("id")))
            cooldown = int(config["cooldown_user_prompts"])
            if isinstance(last, int) and state["prompt_sequence"] - last < cooldown:
                continue
            scored.append((score, lesson))
        scored.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
        selected = [item[1] for item in scored]

    maximum = int(config["max_lessons_per_event"])
    selected = selected[:maximum]
    result = _hook_context(event_name, selected, int(config["max_context_characters"]))
    if result:
        drift_ids = [
            str(lesson.get("id"))
            for lesson in selected
            if isinstance(lesson.get("delivery"), dict)
            and lesson["delivery"].get("mode") == "static"
            and str(lesson.get("id")) not in state["drift_notified"]
        ]
        if drift_ids:
            result["systemMessage"] = (
                "Session Learning detected an unavailable static projection and "
                "delivered it dynamically: " + ", ".join(drift_ids)
            )
            state["drift_notified"].extend(drift_ids)
        for lesson in selected:
            lesson_id = str(lesson.get("id"))
            state["delivered"][lesson_id] = state["prompt_sequence"]
            if lesson_id not in state["relevant"]:
                state["relevant"].append(lesson_id)
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
    root = find_learning_root(cwd_value)
    if root is None:
        return {}
    state_path = _state_path(Path(data_dir).expanduser().resolve(), root, session_id)
    try:
        with _state_lock(state_path):
            return _handle_hook_event_unlocked(
                payload, host=host, data_dir=data_dir, home_dir=home_dir
            )
    except (OSError, TimeoutError):
        return {}


def _validate_destination(
    root: Path,
    value: Any,
    status: Any,
    kind: Any,
    lesson_id: Any,
    label: str,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: destination must be an object"]
    errors: list[str] = []
    destination_type = value.get("type")
    host = value.get("host")
    if destination_type not in DESTINATION_TYPES:
        errors.append(f"{label}: unsupported destination type {destination_type!r}")
    if host not in HOSTS:
        errors.append(f"{label}: destination.host must be 'codex', 'claude', or null")
    path_value = value.get("path")
    if destination_type in {"instruction", "index", "skill", "automation"}:
        errors.extend(_validate_relative_path(root, path_value, f"{label}: destination"))
    elif path_value is not None:
        errors.append(f"{label}: destination.path must be null for type {destination_type!r}")

    expected_active_destination = {
        "guardrail": "instruction",
        "preference": "instruction",
        "project_knowledge": "index",
        "workflow": "skill",
        "invariant": "automation",
    }
    if status == "active" and kind in expected_active_destination:
        expected = expected_active_destination[kind]
        if destination_type != expected:
            errors.append(
                f"{label}: active {kind} lesson requires destination type '{expected}'"
            )

    normalized_path = _normalized_relative(path_value) if isinstance(path_value, str) else ""
    if destination_type in {"instruction", "index", "skill"} and host is None:
        errors.append(f"{label}: native projection requires a codex or claude host")
    if destination_type == "instruction" and isinstance(path_value, str):
        expected_name = "AGENTS.md" if host == "codex" else "CLAUDE.md" if host == "claude" else None
        if expected_name and Path(path_value).name != expected_name:
            errors.append(f"{label}: {host} instruction projection must target {expected_name}")
    if destination_type == "skill" and isinstance(path_value, str):
        expected_prefix = ".agents/skills/" if host == "codex" else ".claude/skills/" if host == "claude" else None
        if expected_prefix and (
            not normalized_path.startswith(expected_prefix) or not normalized_path.endswith("/SKILL.md")
        ):
            host_name = "Codex" if host == "codex" else "Claude"
            errors.append(f"{label}: {host_name} workflow skill must use {expected_prefix}<name>/SKILL.md")
    if destination_type == "index" and normalized_path != ".agents/learning/index.md":
        errors.append(f"{label}: index destination must target .agents/learning/index.md")

    marker = f"session-learning:{lesson_id}"
    if status != "active":
        if destination_type in {"instruction", "skill"} and isinstance(path_value, str):
            projection = root / path_value
            try:
                content = projection.read_text(encoding="utf-8")
            except OSError:
                pass
            else:
                if marker in content:
                    errors.append(f"{label}: inactive lesson remains projected with marker {marker}")
        return errors

    if errors:
        return errors

    if destination_type in {"instruction", "skill"}:
        projection = root / str(path_value)
        try:
            content = projection.read_text(encoding="utf-8")
        except OSError:
            errors.append(f"{label}: active projection is missing at {path_value}")
        else:
            if marker not in content:
                errors.append(f"{label}: active projection is missing projection marker {marker}")
            if destination_type == "skill" and not _has_skill_frontmatter(content):
                errors.append(f"{label}: workflow projection lacks valid SKILL.md frontmatter")
    elif destination_type == "index":
        instruction_path = value.get("instruction_path")
        errors.extend(_validate_relative_path(root, instruction_path, f"{label}: destination.instruction_path"))
        if isinstance(instruction_path, str):
            expected_name = "AGENTS.md" if host == "codex" else "CLAUDE.md" if host == "claude" else None
            if expected_name and Path(instruction_path).name != expected_name:
                host_name = "Codex" if host == "codex" else "Claude"
                errors.append(f"{label}: {host_name} index pointer must target {expected_name}")
        if not errors:
            pointer = root / str(instruction_path)
            try:
                content = pointer.read_text(encoding="utf-8")
            except OSError:
                errors.append(f"{label}: index pointer file is missing at {instruction_path}")
            else:
                if "session-learning:index" not in content:
                    errors.append(f"{label}: index pointer must contain session-learning:index")
    elif destination_type == "automation":
        target = root / str(path_value)
        if not target.exists():
            errors.append(f"{label}: active automation target is missing at {path_value}")
    return errors


def _validate_delivery(
    root: Path,
    value: Any,
    status: Any,
    kind: Any,
    lesson_id: Any,
    label: str,
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
        if kind in expected_modes and mode not in expected_modes[kind]:
            expected = ", ".join(sorted(expected_modes[kind]))
            errors.append(f"{label}: active {kind} lesson requires delivery mode {expected}")

    marker = f"session-learning:{lesson_id}"
    if mode == "dynamic":
        if host is not None or path_value is not None or enforcement_target is not None:
            errors.append(f"{label}: dynamic delivery must not set host, path, or enforcement_target")
        errors.extend(_validate_relative_path(root, instruction_path, f"{label}: delivery.instruction_path"))
        if isinstance(instruction_path, str) and not errors:
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


def _validate_lesson_record(record: dict[str, Any], path: Path, root: Path) -> list[str]:
    label = str(path)
    errors = _require_fields(
        record,
        {
            "schema_version",
            "record_type",
            "id",
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
    if lesson_schema not in {SCHEMA_VERSION, LESSON_SCHEMA_VERSION}:
        errors.append(
            f"{label}: schema_version must be {SCHEMA_VERSION} or {LESSON_SCHEMA_VERSION}"
        )
    if lesson_schema == SCHEMA_VERSION and "destination" not in record:
        errors.append(f"{label}: schema version 1 lesson requires destination")
    if lesson_schema == LESSON_SCHEMA_VERSION and "delivery" not in record:
        errors.append(f"{label}: schema version 2 lesson requires delivery")
    if record.get("record_type") != "lesson":
        errors.append(f"{label}: record_type must be 'lesson'")
    if record.get("kind") not in LESSON_KINDS:
        errors.append(f"{label}: unsupported kind {record.get('kind')!r}")
    if record.get("status") not in LESSON_STATUSES:
        errors.append(f"{label}: unsupported status {record.get('status')!r}")
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

    if lesson_schema == LESSON_SCHEMA_VERSION:
        errors.extend(
            _validate_delivery(
                root,
                record.get("delivery"),
                record.get("status"),
                record.get("kind"),
                record.get("id"),
                label,
            )
        )
    else:
        errors.extend(
            _validate_destination(
                root,
                record.get("destination"),
                record.get("status"),
                record.get("kind"),
                record.get("id"),
                label,
            )
        )
    return errors


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


def rebuild_index(root: str | os.PathLike[str]) -> Path:
    root_path = Path(root).resolve()
    store = store_path(root_path)
    lessons, load_errors = _load_records(store, "lessons")
    if load_errors:
        raise ValueError("; ".join(load_errors))
    if not lessons:
        raise ValueError("cannot rebuild index: no lesson records exist")
    content = render_index(lessons)
    store.mkdir(parents=True, exist_ok=True)
    target = store / "index.md"
    handle, temporary_name = tempfile.mkstemp(prefix="index.", suffix=".tmp", dir=store)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary_name, target)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
    return target


def validate_store(root: str | os.PathLike[str]) -> list[str]:
    root_path = Path(root).resolve()
    store = store_path(root_path)
    if not store.exists():
        return []

    lessons, lesson_load_errors = _load_records(store, "lessons")
    evidence_records, evidence_load_errors = _load_records(store, "evidence")
    cases, case_load_errors = _load_records(store, "cases")
    errors = lesson_load_errors + evidence_load_errors + case_load_errors

    for item in evidence_records:
        errors.extend(_validate_evidence_record(item, Path(item["_path"])))
    for item in lessons:
        errors.extend(_validate_lesson_record(item, Path(item["_path"]), root_path))
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
    elif (store / "index.md").exists():
        errors.append(f"{store / 'index.md'}: index exists without lesson records")
    return sorted(set(errors))


def audit_store(root: str | os.PathLike[str]) -> dict[str, Any]:
    store = store_path(root)
    lessons, lesson_errors = _load_records(store, "lessons")
    evidence_records, evidence_errors = _load_records(store, "evidence")
    _, case_errors = _load_records(store, "cases")
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
        "total_lessons": len(lessons),
        "status_counts": dict(sorted(status_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
        "violations": violations,
        "repeat_corrections": repeat_corrections,
        "unresolved_conflicts": sorted(
            str(item.get("id")) for item in lessons if item.get("status") == "conflicted"
        ),
        "orphan_evidence": sorted(str(item) for item in evidence_ids - referenced_evidence),
        "load_errors": sorted(lesson_errors + evidence_errors + case_errors),
        "validation_errors": validate_store(root),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Rank stored lessons for a query")
    search.add_argument("query", nargs="+", help="Search terms")
    search.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    search.add_argument("--json", action="store_true", help="Emit JSON")
    search.add_argument("--all", action="store_true", help="Include zero-score lessons")

    validate = subparsers.add_parser("validate", help="Validate the learning store")
    validate.add_argument("--root", help="Project root (defaults to Git root or CWD)")

    rebuild = subparsers.add_parser("rebuild-index", help="Regenerate index.md")
    rebuild.add_argument("--root", help="Project root (defaults to Git root or CWD)")

    audit = subparsers.add_parser("audit", help="Summarize learning-store health")
    audit.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    audit.add_argument("--json", action="store_true", help="Emit JSON")

    migrate = subparsers.add_parser("migrate", help="Migrate lesson records to the current schema")
    migrate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    migrate.add_argument("--host", choices=("codex", "claude", "both"), default="codex")

    activate = subparsers.add_parser("activate", help="Activate v2 delivery for a project")
    activate.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    activate.add_argument("--host", choices=("auto", "codex", "claude", "both"), default="auto")

    delivery = subparsers.add_parser("set-delivery", help="Set dynamic or static lesson delivery")
    delivery.add_argument("lesson_id")
    delivery.add_argument("mode", choices=("dynamic", "static"))
    delivery.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    delivery.add_argument("--host", choices=("codex", "claude"), default="codex")

    deactivate = subparsers.add_parser("deactivate", help="Retire a lesson and remove its projection")
    deactivate.add_argument("lesson_id")
    deactivate.add_argument("--root", help="Project root (defaults to Git root or CWD)")

    reactivate = subparsers.add_parser("reactivate", help="Return a retired lesson to candidate status")
    reactivate.add_argument("lesson_id")
    reactivate.add_argument("--root", help="Project root (defaults to Git root or CWD)")

    reconcile = subparsers.add_parser("reconcile-delivery", help="Report or repair delivery drift")
    reconcile.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    reconcile.add_argument("--host", choices=("codex", "claude"), required=True)
    reconcile.add_argument("--apply", action="store_true")

    manifest = subparsers.add_parser("apply-manifest", help="Apply an authoring manifest transactionally")
    manifest.add_argument("manifest")
    manifest.add_argument("--root", help="Project root (defaults to Git root or CWD)")

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
        except (OSError, ValueError, json.JSONDecodeError):
            return 0
        if result:
            print(json.dumps(result, separators=(",", ":")))
        return 0
    root = resolve_project_root(args.root)
    if args.command == "search":
        try:
            results = search_lessons(root, " ".join(args.query), include_all=args.all)
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
        errors = validate_store(root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Valid session-learning store: {store_path(root)}")
        return 0
    if args.command == "rebuild-index":
        try:
            target = rebuild_index(root)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(target)
        return 0
    if args.command == "audit":
        audit = audit_store(root)
        if args.json:
            print(json.dumps(audit, indent=2, sort_keys=True))
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
        return 1 if audit["load_errors"] or audit["validation_errors"] else 0
    if args.command == "migrate":
        print(json.dumps(migrate_store(root, host=args.host), indent=2, sort_keys=True))
        return 0
    if args.command == "activate":
        print(json.dumps(activate_store(root, host=args.host), indent=2, sort_keys=True))
        return 0
    if args.command == "set-delivery":
        print(
            json.dumps(
                set_delivery(root, args.lesson_id, args.mode, host=args.host),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "deactivate":
        print(json.dumps(deactivate_lesson(root, args.lesson_id), indent=2, sort_keys=True))
        return 0
    if args.command == "reactivate":
        print(json.dumps(reactivate_lesson(root, args.lesson_id), indent=2, sort_keys=True))
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
            result = apply_manifest(root, manifest_value)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
