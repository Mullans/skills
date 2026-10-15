"""Persistent cooperative resource claims; standard-library Python 3.10+.

All contenders must use the same state directory on a filesystem providing
atomic mkdir and replace. This is coordination, not OS access control.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from uuid import UUID, uuid4

LEDGER = "resource_lock.md"
GUARD = ".resource_lock.guard"
START = "<!-- resource-lock-json\n"
END = "\n-->"
MAX_BYTES = 1024 * 1024
GUARD_WAIT = 5.0


class LockError(Exception):
    """A condition that blocks safe coordination."""

    def __init__(self, message, result=None):
        super().__init__(message)
        self.result = result


def clean(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise LockError(f"{label} must be text")
    value = " ".join(value.split())
    if not value or len(value) > 500 or "-->" in value:
        raise LockError(f"{label} must be 1-500 characters without '-->'")
    return value


def resource_name(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
        raise LockError("Resource names must be 1-64 lowercase letters, digits or hyphens")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def validate(state: dict) -> dict:
    if not isinstance(state, dict) or set(state) != {"version", "resources", "claims"}:
        raise LockError("Invalid ledger structure; stop and inspect")
    if type(state["version"]) is not int or state["version"] != 2:
        raise LockError("Unsupported ledger version; no automatic migration")
    resources, claims = state["resources"], state["claims"]
    if not isinstance(resources, dict) or not resources:
        raise LockError("Ledger needs explicit resource scopes")
    for name, scope in resources.items():
        resource_name(name)
        if clean(scope, "Scope") != scope:
            raise LockError("Invalid resource scope")
    if not isinstance(claims, list) or len(claims) > len(resources):
        raise LockError("Invalid claim list")
    held, ids = set(), set()
    for item in claims:
        if not isinstance(item, dict) or set(item) != {
            "resources", "claim_id", "owner", "reason", "claimed_at"
        }:
            raise LockError("Invalid claim fields")
        names = item["resources"]
        if (not isinstance(names, list) or not names
                or any(not isinstance(n, str) or n not in resources for n in names)
                or len(names) != len(set(names)) or held.intersection(names)):
            raise LockError("Invalid or overlapping resource claim")
        for key in ("owner", "reason"):
            if clean(item[key], key) != item[key]:
                raise LockError(f"Invalid {key}")
        try:
            if str(UUID(item["claim_id"])) != item["claim_id"]:
                raise ValueError("Noncanonical claim ID")
            stamp = datetime.fromisoformat(item["claimed_at"])
            if stamp.utcoffset() is None:
                raise ValueError("Missing timezone")
        except (ValueError, TypeError, AttributeError) as exc:
            raise LockError("Invalid claim identity or timestamp") from exc
        if item["claim_id"] in ids:
            raise LockError("Duplicate claim ID")
        held.update(names)
        ids.add(item["claim_id"])
    return state


def read(root: Path) -> dict:
    try:
        path = root / LEDGER
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Ledger exceeds 1 MiB")
        text = path.read_text(encoding="utf-8")
        if text.count(START) != 1:
            raise ValueError("Expected one state marker")
        payload, separator, tail = text.split(START, 1)[1].partition(END)
        if not separator or tail.strip():
            raise ValueError("Invalid state marker ending")
        return validate(json.loads(payload, object_pairs_hook=unique_object))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise LockError(f"Cannot read {root / LEDGER}; stop and inspect: {exc}") from exc


def render(state: dict) -> str:
    validate(state)
    lines = [
        "# Shared resource checkout", "",
        "Managed by resource_lock.py. The JSON block is authoritative.",
        "Procedure: docs/resource-checkout.md in the coordinating project.", "",
        "## Resource scopes", "",
    ]
    for name, scope in sorted(state["resources"].items()):
        lines.append(f"- {name}: {scope}")
    lines.extend(["", "## Active claims", ""])
    for item in state["claims"]:
        lines.extend([
            f"### {', '.join(item['resources'])}", "",
            f"- Claim ID: {item['claim_id']}",
            f"- Owner: {item['owner']}",
            f"- Reason: {item['reason']}",
            f"- Claimed (UTC): {item['claimed_at']}", "",
        ])
    if not state["claims"]:
        lines.extend(["_None._", ""])
    lines.extend([
        START.rstrip(), json.dumps(state, sort_keys=True, ensure_ascii=True), "-->", "",
    ])
    return "\n".join(lines)


@contextmanager
def guard(root: Path):
    """Never clear an existing guard. Wait briefly, then fail closed."""
    path = root / GUARD
    deadline = time.monotonic() + GUARD_WAIT
    while True:
        try:
            path.mkdir()
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise LockError(f"Guard busy or abandoned: {path}; user recovery required")
            time.sleep(0.05)
        except OSError as exc:
            raise LockError(f"Cannot acquire guard at {path}: {exc}") from exc
    try:
        yield
    finally:
        path.rmdir()  # Remove only the guard successfully created by this call.


def write(root: Path, state: dict) -> None:
    """Caller must hold guard. Atomic replacement retains the old ledger on error."""
    content = render(state)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise LockError("Ledger would exceed 1 MiB")
    descriptor, temporary = tempfile.mkstemp(prefix=".resource_lock-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, root / LEDGER)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def init(root: Path, resources: dict[str, str]) -> dict:
    state = validate({"version": 2, "resources": resources, "claims": []})
    with guard(root):
        if os.path.lexists(root / LEDGER):
            raise LockError("Ledger already exists; initialization never resets it")
        write(root, state)
    return state


def status(root: Path) -> dict:
    # An abandoned mutation guard blocks status as well as writes.
    with guard(root):
        state = read(root)
        return dict(state, results=[resource_result(state, name) for name in state["resources"]])


def resource_result(state, name):
    holder = next((c for c in state["claims"] if name in c["resources"]), None)
    return dict(resource=name, status="held" if holder else "available",
                owner=holder["owner"] if holder else None,
                claim_id=holder["claim_id"] if holder else None)


def selected(state: dict, resources) -> list[str]:
    names = list(resources)
    if (not names or any(not isinstance(n, str) or n not in state["resources"] for n in names)
            or len(names) != len(set(names))):
        raise LockError("Select distinct, registered resources")
    return sorted(names)


def claim(root: Path, owner: str, reason: str, resources) -> dict:
    owner, reason = clean(owner, "Owner"), clean(reason, "Reason")
    with guard(root):
        state = read(root)
        names = selected(state, resources)
        results = [resource_result(state, name) for name in names]
        if any(row["status"] == "held" for row in results):
            for row in results:
                if row["status"] == "available":
                    row["status"] = "available_not_acquired"
            raise LockError("Requested resources conflict; nothing acquired",
                            dict(ok=False, results=results))
        item = {
            "resources": names, "claim_id": str(uuid4()), "owner": owner,
            "reason": reason, "claimed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        state["claims"].append(item)
        write(root, state)
        return item


def owned(state: dict, owner: str, claim_id: str) -> dict:
    item = next((c for c in state["claims"] if c["claim_id"] == claim_id), None)
    if item is None or item["owner"] != owner:
        raise LockError("Owner and claim ID do not match an active checkout")
    return item


def verify(root: Path, owner: str, claim_id: str, resources) -> dict:
    with guard(root):
        state = read(root)
        names = selected(state, resources)
        item = owned(state, owner, claim_id)
        if not set(names).issubset(item["resources"]):
            raise LockError("This claim does not cover every requested resource")
        return item


def verify_many(root: Path, owner: str, claim_ids, resources) -> dict:
    """Action-helper assertion over one guarded snapshot; no agent preflight."""
    ids = {claim_ids} if isinstance(claim_ids, str) else set(claim_ids)
    with guard(root):
        state = read(root)
        names = selected(state, resources)
        for name in names:
            row = resource_result(state, name)
            if row["owner"] != owner or row["claim_id"] not in ids:
                raise LockError(f"Claim identity does not cover {name}")
        return {name: resource_result(state, name) for name in names}


def release(root: Path, owner: str, claim_id, evidence=None, *, resources=None) -> dict:
    """Release owned selections and confirm under one guard; evidence is ignored."""
    owner = clean(owner, "Owner")
    ids = [claim_id] if isinstance(claim_id, str) else list(claim_id)
    if not ids or any(not isinstance(value, str) or not value for value in ids):
        raise LockError("Supply one or more claim IDs")
    ids = list(dict.fromkeys(ids))
    with guard(root):
        state = read(root)
        if resources is None:
            names = [name for c in state["claims"] if c["claim_id"] in ids
                     for name in c["resources"]]
        else:
            names = selected(state, resources)
        results, removals = [], set()
        for name in names:
            row = resource_result(state, name)
            if row["status"] == "available":
                row["status"] = "already_absent"
            elif row["owner"] == owner and row["claim_id"] in ids:
                row["status"] = "pending"
                removals.add(name)
            else:
                row["status"] = "ownership_mismatch"
            results.append(row)
        for value in ids:
            if not any(c["claim_id"] == value for c in state["claims"]):
                results.append(dict(claim_id=value, status="already_absent"))
        if removals:
            remaining = []
            for item in state["claims"]:
                kept = [name for name in item["resources"] if name not in removals]
                if kept:
                    remaining.append(dict(item, resources=kept))
            state["claims"] = remaining
            write_error = None
            try:
                write(root, state)
            except (OSError, LockError) as exc:
                write_error = str(exc)
            try:
                confirmed = read(root)
            except (OSError, LockError) as exc:
                for row in results:
                    if row["status"] == "pending":
                        row.update(status="confirmation_failure", error=str(exc))
                        if write_error:
                            row["update_error"] = write_error
            else:
                for row in results:
                    if row["status"] == "pending":
                        still_present = resource_result(confirmed, row["resource"])["claim_id"]
                        row["status"] = "released" if still_present is None else "update_failure"
                        if write_error:
                            row["update_error"] = write_error
        ok = all(row["status"] in ("released", "already_absent") for row in results)
        # A failed update is never reported as a wholly successful operation, even
        # when rereading establishes that replacement completed before the error.
        ok = ok and not any("update_error" in row for row in results)
        return dict(ok=ok, results=results)


def refresh(root: Path) -> None:
    with guard(root):
        write(root, read(root))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path.cwd(),
                        help="One shared authority directory; defaults to current directory")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("init", help="Create a NEW ledger; never overwrite")
    start.add_argument("--resource", action="append", required=True, metavar="NAME=SCOPE")
    sub.add_parser("status", help="Optional inspection of all registered resources")
    sub.add_parser("refresh-display")
    take = sub.add_parser("claim", help="Atomically acquire all requested resources")
    take.add_argument("--resource", action="append", required=True)
    take.add_argument("--owner", required=True)
    take.add_argument("--reason", required=True)
    give = sub.add_parser("release", help="Release owned selections and confirm removals")
    give.add_argument("--owner", required=True)
    give.add_argument("--claim-id", action="append", required=True)
    give.add_argument("--resource", action="append", help="Omit to release all supplied claims")
    give.add_argument("--evidence", type=Path, help="Ignored compatibility input")
    args = parser.parse_args(argv)
    try:
        root = args.state_dir.resolve(strict=True)
        if not root.is_dir():
            raise LockError("State directory must exist")
        if args.command == "init":
            definitions = {}
            for entry in args.resource:
                name, separator, scope = entry.partition("=")
                resource_name(name)
                if not separator or name in definitions:
                    raise LockError("Use distinct NAME=SCOPE resource definitions")
                definitions[name] = clean(scope, "Scope")
            result = init(root, definitions)
        elif args.command == "status":
            result = status(root)
        elif args.command == "refresh-display":
            refresh(root)
            result = {"refreshed": True}
        elif args.command == "claim":
            result = claim(root, args.owner, args.reason, args.resource)
        else:
            result = release(root, args.owner, args.claim_id, args.evidence, resources=args.resource)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("ok", True) else 2
    except (LockError, OSError) as exc:
        if isinstance(exc, LockError) and exc.result is not None:
            print(json.dumps(exc.result, sort_keys=True))
        print(f"Checkout blocked: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
