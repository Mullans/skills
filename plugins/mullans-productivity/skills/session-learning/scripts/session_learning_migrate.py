#!/usr/bin/env python3
"""Migrate session-learning records to the schema bundled with this skill."""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sys
from typing import Any

import session_learning as engine


def migrate_lesson(
    record: dict[str, Any], *, authority: str, host: str
) -> dict[str, Any]:
    migrated = engine.upgrade_lesson_record(record, authority=authority, host=host)
    original_schema = record.get("schema_version")
    original_version = record.get("version")
    if (
        original_schema != engine.LESSON_SCHEMA_VERSION
        or not isinstance(original_version, str)
        or not engine.SKILL_VERSION_PATTERN.fullmatch(original_version)
        or engine.skill_version_key(original_version)
        < engine.skill_version_key(engine.SKILL_VERSION)
    ):
        migrated["version"] = engine.SKILL_VERSION
    return migrated


def _migrate_evidence(record: dict[str, Any], authority: str) -> dict[str, Any]:
    version = record.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError("evidence schema_version must be an integer")
    if version > engine.EVIDENCE_SCHEMA_VERSION:
        raise ValueError(
            f"evidence schema_version {version} is newer than supported version "
            f"{engine.EVIDENCE_SCHEMA_VERSION}"
        )
    migrated = copy.deepcopy(record)
    if version == 1:
        migrated["schema_version"] = 2
        migrated["authority"] = authority
        version = 2
    if version != engine.EVIDENCE_SCHEMA_VERSION:
        raise ValueError(f"no evidence migration registered from schema_version {version}")
    return migrated


def _projection_changes(
    root: Path,
    original: dict[str, Any],
    migrated: dict[str, Any],
    pending: dict[Path, bytes | None],
) -> None:
    destination = original.get("destination")
    if not isinstance(destination, dict) or destination.get("type") != "instruction":
        return
    old_path = destination.get("path")
    if not isinstance(old_path, str) or migrated.get("delivery", {}).get("mode") != "dynamic":
        return
    target = root / old_path
    current_bytes = pending.get(target)
    current = (
        current_bytes.decode("utf-8")
        if isinstance(current_bytes, bytes)
        else target.read_text(encoding="utf-8") if target.exists() else ""
    )
    updated = engine._remove_marker_block(current, f"session-learning:{migrated.get('id')}")
    pending[target] = updated.encode("utf-8")


def _migrate_authority(
    root: Path,
    *,
    authority: str,
    home_dir: str | os.PathLike[str] | None,
    host: str,
) -> dict[str, Any]:
    store = engine.store_path(root, authority=authority, home_dir=home_dir)
    confinement = root if authority == "project" else store
    if not store.exists():
        return {"authority": authority, "changed": False, "files": [], "lessons": []}
    with engine.writer_lock(root, authority=authority):
        engine.recover_transactions(confinement, transaction_store=store)
        lessons, lesson_errors = engine._load_records(store, "lessons")
        evidence, evidence_errors = engine._load_records(store, "evidence")
        errors = lesson_errors + evidence_errors
        if errors:
            raise ValueError("; ".join(errors))
        changes: dict[Path, bytes | None] = {}
        migrated_lessons: list[dict[str, Any]] = []
        changed_ids: list[str] = []
        for item in lessons:
            original = engine._public_record(item)
            migrated = migrate_lesson(original, authority=authority, host=host)
            migrated_lessons.append(migrated)
            if migrated != original:
                path = Path(item["_path"])
                changes[path] = engine._json_bytes(migrated)
                _projection_changes(root, original, migrated, changes)
                changed_ids.append(str(migrated.get("id", path.stem)))
        for item in evidence:
            original = engine._public_record(item)
            migrated = _migrate_evidence(original, authority)
            if migrated != original:
                changes[Path(item["_path"])] = engine._json_bytes(migrated)
        if changed_ids:
            changes.update(
                engine._derived_changes(store, migrated_lessons, authority=authority)
            )
            if authority == "project":
                for lesson in migrated_lessons:
                    delivery = lesson.get("delivery")
                    if (
                        lesson.get("status") == "active"
                        and isinstance(delivery, dict)
                        and delivery.get("mode") == "dynamic"
                        and isinstance(delivery.get("instruction_path"), str)
                    ):
                        pointer = root / delivery["instruction_path"]
                        pending = changes.get(pointer)
                        content = (
                            pending.decode("utf-8")
                            if isinstance(pending, bytes)
                            else pointer.read_text(encoding="utf-8") if pointer.exists() else ""
                        )
                        changes[pointer] = engine._ensure_pointer(content).encode("utf-8")
        if not changes:
            return {"authority": authority, "changed": False, "files": [], "lessons": []}
        written = engine.apply_file_transaction(
            confinement,
            changes,
            transaction_store=store,
            validator=lambda: engine.validate_store(root, authority=authority, home_dir=home_dir),
        )
    return {
        "authority": authority,
        "changed": bool(written),
        "files": [path.relative_to(confinement).as_posix() for path in written],
        "lessons": sorted(changed_ids),
    }


def migrate_store(
    root: str | os.PathLike[str],
    *,
    authority: str = "both",
    home_dir: str | os.PathLike[str] | None = None,
    host: str = "codex",
) -> dict[str, Any]:
    if authority not in engine.AUTHORITIES | {"both"}:
        raise ValueError("authority must be project, local, or both")
    if host not in {"codex", "claude"}:
        raise ValueError("host must be codex or claude")
    root_path = Path(root).expanduser().resolve()
    authorities = ("project", "local") if authority == "both" else (authority,)
    results = [
        _migrate_authority(
            root_path,
            authority=item,
            home_dir=home_dir,
            host=host,
        )
        for item in authorities
    ]
    return {
        "lesson_schema_version": engine.LESSON_SCHEMA_VERSION,
        "changed": any(result["changed"] for result in results),
        "authorities": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Project root (defaults to Git root or CWD)")
    parser.add_argument("--authority", choices=("project", "local", "both"), default="both")
    parser.add_argument("--home-dir")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    args = parser.parse_args(argv)
    try:
        result = migrate_store(
            engine.resolve_project_root(args.root),
            authority=args.authority,
            home_dir=args.home_dir,
            host=args.host,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
