"""Prepare an isolated fixture, then check it inside a native Codex sandbox.

Run --prepare from the normal terminal before starting the sandbox. Never use
real personal/configuration stores. This helper is maintainer-only.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

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


def check_windows_lock(target: Path) -> str:
    """Hold a real Windows handle without delete sharing, then release it."""
    if sys.platform != 'win32':
        return 'not executed: requires native Windows'
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    def lock():
        handle = kernel.CreateFileW(str(target), 0x80000000, 3, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle
    before = target.read_bytes()
    handle = lock()
    started = time.monotonic()
    try:
        try:
            engine._atomic_write_bytes(target, b'locked replacement\n')
        except OSError as exc:
            assert exc.winerror in (5, 32, 33)
            assert target.read_bytes() == before
            assert time.monotonic() - started < 3
        else:
            raise AssertionError('Expected a persistent sharing denial')
    finally:
        kernel.CloseHandle(handle)
    handle = lock()
    timer = threading.Timer(0.1, kernel.CloseHandle, args=(handle,))
    timer.start()
    try:
        engine._atomic_write_bytes(target, b'released replacement\n')
        assert target.read_bytes() == b'released replacement\n'
    finally:
        timer.join()
        engine._atomic_write_bytes(target, before)
    return 'persistent lock failed safely; released lock succeeded automatically'


def check(root: Path, *, writes_only: bool = False, repeat: int = 1, windows_lock: bool = False) -> dict[str, str]:
    if not (root / 'permission-fixture.json').is_file():
        raise ValueError('Only a prepared isolated fixture may be checked')
    result = {}
    target = root / '.session-learning/probe.json'
    original = target.read_bytes()
    try:
        for _ in range(repeat):
            engine._atomic_write_bytes(target, b'replaced\n')
            assert target.read_bytes() == b'replaced\n'
            try:
                engine.apply_file_transaction(root, {target: b'failed\n'}, validator=lambda: ['injected validation failure'])
            except ValueError:
                assert target.read_bytes() == b'replaced\n'
            else:
                raise AssertionError('Expected validation failure')
        result['atomic_replace'] = f'passed {repeat} times'
        result['rollback'] = f'passed {repeat} times'
        if windows_lock:
            result['windows_sharing_lock'] = check_windows_lock(target)
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
    parser.add_argument('--repeat', type=int, default=1, help='Repeat replacement and rollback checks (1-1000)')
    parser.add_argument('--windows-lock-check', action='store_true', help='Check persistent and released native Windows sharing locks')
    args = parser.parse_args()
    if not 1 <= args.repeat <= 1000:
        parser.error('--repeat must be between 1 and 1000')
    root = args.root.resolve()
    try:
        if args.prepare:
            prepare(root)
            print('Prepared isolated permission fixture')
        else:
            print(json.dumps(check(root, writes_only=args.writes_only, repeat=args.repeat, windows_lock=args.windows_lock_check), indent=2))
    except (OSError, ValueError, AssertionError) as exc:
        print(f'Permission validation failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
