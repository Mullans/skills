#!/usr/bin/env python3
"""Render the Codex and Claude hook adapters from one semantic event table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


EVENTS: dict[str, dict[str, str | None]] = {
    "UserPromptSubmit": {"claude_matcher": None, "codex_matcher": None},
    "PreToolUse": {
        "claude_matcher": "Bash|PowerShell|Read|Glob|Grep|Edit|Write",
        "codex_matcher": "Bash|PowerShell|apply_patch|Read|Glob|Grep|Edit|Write",
    },
    "SessionStart": {
        "claude_matcher": "startup|resume|clear|compact|fork",
        "codex_matcher": "startup|resume|clear|compact",
    },
    "SessionEnd": {"claude_matcher": None, "codex_matcher": None},
}


def _claude_handler(event: str) -> dict[str, Any]:
    arguments = ["${CLAUDE_PLUGIN_ROOT}/bin/session-learning-hook.js"]
    if event == "SessionStart":
        arguments.append("--warn-missing-python")
    arguments.extend(["--host", "claude"])
    return {
        "type": "command",
        "command": "node",
        "args": arguments,
        "timeout": 2,
    }


def _codex_handler(event: str) -> dict[str, Any]:
    warning = " --warn-missing-python" if event == "SessionStart" else ""
    handler: dict[str, Any] = {
        "type": "command",
        "command": (
            'sh "${PLUGIN_ROOT}/bin/session-learning-hook"'
            f"{warning} --host codex"
        ),
        "commandWindows": (
            '"${PLUGIN_ROOT}\\bin\\session-learning-hook.cmd"'
            f"{warning} --host codex"
        ),
        "timeout": 2,
    }
    if event != "SessionEnd":
        handler["additionalContextLimit"] = 4000
    return handler


def _config(host: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event, values in EVENTS.items():
        matcher = values[f"{host}_matcher"]
        group: dict[str, Any] = {}
        if matcher is not None:
            group["matcher"] = matcher
        group["hooks"] = [
            _claude_handler(event) if host == "claude" else _codex_handler(event)
        ]
        groups[event] = [group]
    return {
        "description": "Inject relevant evidence-backed project lessons without blocking host actions.",
        "hooks": groups,
    }


def rendered_files(repo_root: Path) -> dict[Path, str]:
    plugin_root = repo_root / "plugins" / "mullans-productivity"
    return {
        plugin_root / "hooks" / "claude.json": json.dumps(_config("claude"), indent=2) + "\n",
        plugin_root / "hooks" / "codex.json": json.dumps(_config("codex"), indent=2) + "\n",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    mismatches: list[Path] = []
    for path, expected in rendered_files(args.root.resolve()).items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == expected:
            continue
        mismatches.append(path)
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    if mismatches and not args.write:
        for path in mismatches:
            print(f"out of date: {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
