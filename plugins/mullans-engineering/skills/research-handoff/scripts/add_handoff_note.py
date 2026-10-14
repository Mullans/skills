"""Append a cross-effort request to an existing Markdown handoff (stdlib only)."""
import argparse
from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time

HEADING = "## Handoff notes"
LABELS = {"agent": "Agent request", "user": "User request"}
ENTRY = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2}) · (Agent request|User request) · (.+?):\*\* (.+)$")


def single_line(value, field):
    value = value.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError(f"{field} must be a nonempty single line")
    return value


def render_note(request_type, source, request, note_date, context=None):
    if request_type not in LABELS:
        raise ValueError("request type must be agent or user")
    if date.fromisoformat(note_date).isoformat() != note_date:
        raise ValueError("date must use YYYY-MM-DD")
    source = single_line(source, "source")
    request = single_line(request, "request")
    if "*" in source or "·" in source:
        raise ValueError("source cannot contain '*' or '·'")
    note = f"- **{note_date} · {LABELS[request_type]} · {source}:** {request}"
    if context is not None:
        context = single_line(context, "context")
        if "<" in context or ">" in context:
            raise ValueError("context cannot contain angle brackets")
        note += f" [Context](<{context}>)"
    return note


def section_bounds(text):
    """Find actual headings, ignoring fenced examples."""
    start = None
    fence = None
    offset = 0
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                if not line[marker.end():].strip():
                    fence = None
        elif marker:
            fence = marker[1]
        else:
            heading = re.match(r"^ {0,3}(#{1,2})[ \t]+(.+?)[ \t]*(?:[ \t]+#+)?\r?\n?$", line)
            if heading:
                title = heading[2].strip()
                if len(heading[1]) == 2 and title == "Handoff notes":
                    if start is not None:
                        raise ValueError("multiple Handoff notes sections; reconcile before appending")
                    start = offset + len(line)
                elif start is not None:
                    # Check the remainder for duplicate sections as well.
                    rest = text[offset:]
                    other_start, _ = section_bounds(rest)
                    if other_start is not None:
                        raise ValueError("multiple Handoff notes sections; reconcile before appending")
                    return start, offset
        offset += len(line)
    return start, len(text)


def request_key(note):
    match = ENTRY.fullmatch(note.strip())
    if not match:
        return None
    request = re.sub(r" \[Context\]\(<.*>\)$", "", match[4])
    return tuple(" ".join(part.split()).casefold() for part in (match[2], match[3], request))


def insertion(original, note):
    text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    start, end = section_bounds(text)
    if start is not None:
        for line in text[start:end].splitlines():
            if request_key(line) == request_key(note):
                return original, "already-present"
        prefix, suffix = text[:end], text[end:]
        separator = "" if prefix.endswith(newline * 2) else (newline if prefix.endswith(newline) else newline * 2)
        return (prefix + separator + note + newline + (newline if suffix else "") + suffix).encode("utf-8"), "added"
    separator = "" if text.endswith(newline * 2) else (newline if text.endswith(newline) else newline * 2)
    return (text + separator + HEADING + newline * 2 + note + newline).encode("utf-8"), "added"


@contextmanager
def handoff_lock(path, timeout=10):
    """Serialize helper writers. Never steal a stale or another writer's lock."""
    lock = path.with_name(path.name + ".handoff-notes.lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"handoff note lock is busy: {lock}; inspect its owner before recovery")
            time.sleep(0.05)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "handoff": str(path)}, handle)
        yield
    finally:
        lock.unlink()


def add_note(path, note, dry_run=False, lock_timeout=10):
    path = Path(path).absolute()
    if path.suffix.lower() != ".md" or path.is_symlink() or not path.is_file():
        raise ValueError("handoff must be an existing regular Markdown file, not a symlink")
    if dry_run:
        _, status = insertion(path.read_bytes(), note)
        return {"status": status, "dry_run": True, "handoff": str(path), "note": note}
    with handoff_lock(path, lock_timeout):
        original_stat = path.stat()
        if not stat.S_ISREG(original_stat.st_mode):
            raise ValueError("handoff is no longer a regular file")
        original = path.read_bytes()
        updated, status = insertion(original, note)
        if status == "already-present":
            return {"status": status, "handoff": str(path), "note": note}
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
            current_stat = path.stat()
            identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)
            if path.is_symlink() or identity(current_stat) != identity(original_stat) or path.read_bytes() != original:
                raise RuntimeError("handoff changed during insertion; no replacement written")
            os.replace(temporary, path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)
    return {"status": status, "handoff": str(path), "note": note}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff", type=Path)
    parser.add_argument("--request-type", choices=LABELS, required=True)
    parser.add_argument("--source", required=True, help="Originating effort")
    parser.add_argument("--request", required=True, help="Self-contained request in one line")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD; defaults to local date")
    parser.add_argument("--context", help="Optional Markdown destination relative to the handoff, or URL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing or taking a lock")
    args = parser.parse_args()
    try:
        note = render_note(args.request_type, args.source, args.request, args.date, args.context)
        result = add_note(args.handoff, note, args.dry_run)
    except (OSError, ValueError, RuntimeError, TimeoutError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
