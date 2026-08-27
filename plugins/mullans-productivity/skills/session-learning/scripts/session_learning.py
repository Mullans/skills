#!/usr/bin/env python3
"""Inspect and validate a project's session-learning store.

The helper is deliberately deterministic and dependency-free. Reasoning about
what a session taught remains the agent's job; this module makes storage,
search, indexing, and validation repeatable.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Iterable


SCHEMA_VERSION = 1
STORE_RELATIVE = Path(".agents") / "learning"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

LESSON_KINDS = {"guardrail", "workflow", "project_knowledge", "preference", "invariant"}
LESSON_STATUSES = {"candidate", "active", "conflicted", "superseded", "retired"}
DESTINATION_TYPES = {"instruction", "index", "skill", "automation", "evidence_only", "none"}
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
            "destination",
            "provenance",
            "relationships",
            "usage",
            "timestamps",
        },
        label,
    )
    errors.extend(_validate_id(record, path, label))
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version must be {SCHEMA_VERSION}")
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
            statement = " ".join(str(record.get("statement", "")).split())
            lines.append(
                f"- [`{record_id}`](lessons/{record_id}.json) — **{kind}** · {status} · `{scope}` — {statement}"
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
