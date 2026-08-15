"""Reusable path access checks for CLI and programmatic use."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from mark2word.errors import Mark2WordError

_WIN_ERROR_ACCESS_DENIED = 5
_WIN_ERROR_SHARING_VIOLATION = 32


def _err(message: str) -> Mark2WordError:
    if message.startswith("Error:"):
        return Mark2WordError(message)
    return Mark2WordError(f"Error: {message}")


def _is_read_only(path: Path) -> bool:
    if os.name == "nt":
        import ctypes

        FILE_ATTRIBUTE_READONLY = 0x1
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != 0xFFFFFFFF and attrs & FILE_ATTRIBUTE_READONLY:
            return True
    mode = path.stat().st_mode
    return not (mode & stat.S_IWUSR or mode & stat.S_IWGRP or mode & stat.S_IWOTH)


def _probe_existing_writable(out_path: Path) -> None:
    if os.name == "nt":
        _probe_existing_writable_windows(out_path)
        return
    try:
        with open(out_path, "r+b"):
            pass
    except PermissionError as exc:
        raise _err(
            f"cannot write to {out_path}: the file is open in another program "
            "(close it and try again)"
        ) from exc


def _probe_existing_writable_windows(out_path: Path) -> None:
    import ctypes

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        str(out_path),
        GENERIC_READ | GENERIC_WRITE,
        0,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle in (INVALID_HANDLE_VALUE, -1):
        err = kernel32.GetLastError()
        if err in (_WIN_ERROR_ACCESS_DENIED, _WIN_ERROR_SHARING_VIOLATION):
            raise _err(
                f"cannot write to {out_path}: the file is open in another program "
                "(close it and try again)"
            )
        raise OSError(err, "CreateFileW", str(out_path))
    kernel32.CloseHandle(handle)


def ensure_input_readable(path: Path, *, kind: str = "input") -> None:
    """Verify a markdown or theme file exists and can be read."""
    resolved = path.resolve()
    label = "markdown" if kind == "input" else kind
    if not resolved.exists():
        raise _err(f"cannot read {label} file {resolved}: file not found")
    if not resolved.is_file():
        raise _err(f"cannot read {label} file {resolved}: not a file")
    if not os.access(resolved, os.R_OK):
        raise _err(f"cannot read {label} file {resolved}: permission denied")


def ensure_output_writable(out_path: Path) -> None:
    """Fail fast when the output .docx cannot be created or overwritten."""
    resolved = out_path.resolve()
    parent = resolved.parent
    parent.mkdir(parents=True, exist_ok=True)
    if not os.access(parent, os.W_OK):
        raise _err(
            f"cannot write to {resolved}: the output directory is not writable ({parent})"
        )

    if resolved.exists():
        if resolved.is_dir():
            raise _err(
                f"cannot write to {resolved}: path is a directory, expected a .docx file"
            )
        if _is_read_only(resolved):
            raise _err(
                f"cannot write to {resolved}. A read-only file already exists at that "
                "location. Delete it or pick another path."
            )
        try:
            _probe_existing_writable(resolved)
        except OSError as exc:
            raise _err(f"cannot write to {resolved}: {exc}") from exc


def raise_if_output_write_blocked(out_path: Path, exc: BaseException) -> None:
    """Re-run output checks after a failed save (race with another program)."""
    resolved = out_path.resolve()
    if resolved.exists() and _is_read_only(resolved):
        raise _err(
            f"cannot write to {resolved}. A read-only file already exists at that "
            "location. Delete it or pick another path."
        ) from exc
    if isinstance(exc, PermissionError):
        raise _err(
            f"cannot write to {resolved}: the file is open in another program "
            "(close it and try again)"
        ) from exc
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (13, _WIN_ERROR_ACCESS_DENIED):
        raise _err(
            f"cannot write to {resolved}: the file is open in another program "
            "(close it and try again)"
        ) from exc
    raise exc
