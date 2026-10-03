"""Prepare an isolated fixture, then check it inside a native Codex sandbox.

Run --prepare from the normal terminal before starting the sandbox. Never use
real personal/configuration stores. This helper is maintainer-only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'plugins/mullans-productivity/skills/session-learning/scripts/session_learning.py'
spec = importlib.util.spec_from_file_location('permission_engine', SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)


def prepare(root: Path) -> None:
    if root.exists():
        raise ValueError('Use a fresh isolated fixture path')
    root.mkdir(parents=True)
    for location in ('.agents', '.codex', '.session-learning'):
        (root / location).mkdir()
    (root / 'permission-fixture.json').write_text('{"schema_version": 1}')
    (root / '.session-learning/probe.json').write_bytes(b'original\n')


def check(root: Path, *, writes_only: bool = False) -> dict[str, str]:
    if not (root / 'permission-fixture.json').is_file():
        raise ValueError('Only a prepared isolated fixture may be checked')
    result = {}
    target = root / '.session-learning/probe.json'
    original = target.read_bytes()
    try:
        engine._atomic_write_bytes(target, b'replaced\n')
        assert target.read_bytes() == b'replaced\n'
        result['atomic_replace'] = 'passed'
        try:
            engine.apply_file_transaction(root, {target: b'failed\n'}, validator=lambda: ['injected validation failure'])
        except ValueError:
            assert target.read_bytes() == b'replaced\n'
            result['rollback'] = 'passed'
        else:
            raise AssertionError('Expected validation failure')
    finally:
        if target.read_bytes() != original:
            engine._atomic_write_bytes(target, original)
    if not writes_only:
        for location in ('.agents', '.codex'):
            probe = root / location / 'permission-probe.txt'
            try:
                engine._atomic_write_bytes(probe, b'temporary probe\n')
            except PermissionError:
                result[location] = 'denied as expected'
            else:
                probe.unlink()
                raise AssertionError(f'{location} was writable; not the expected protected-path policy')
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--writes-only', action='store_true', help='Exercise ordinary outer-session writes without assuming nested protected roots')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.prepare:
            prepare(root)
            print('Prepared isolated permission fixture')
        else:
            print(json.dumps(check(root, writes_only=args.writes_only), indent=2))
    except (OSError, ValueError, AssertionError) as exc:
        print(f'Permission validation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
