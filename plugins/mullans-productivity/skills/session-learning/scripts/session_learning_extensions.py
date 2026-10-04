"""Conditional drafting, private configuration, activity, and reflection helpers.

The canonical engine owns transactions. This module owns staging and read-only
views; it never runs model inference or searches conversation history.
"""
from __future__ import annotations

from collections import Counter
import copy
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid

REVIEWABLE = {"pending", "deferred"}
DISPOSITIONS = REVIEWABLE | {"accepted", "dismissed"}
REASONS = {"useful_new", "useful_refinement", "confirmation", "low_impact",
           "duplicate", "already_enforced", "unsupported", "verification_gap"}
MAX_DRAFT_BYTES = 8192
MAX_ACTIVITY_BYTES = 1024 * 1024
ACTIVITY_COUNTERS = {"hook_events", "context_emissions", "context_characters", "lesson_emissions", "lesson_characters",
    "drafting_pointer_emissions", "drafting_pointer_characters", "drafting_revocations", "drafting_revocation_characters",
    "drafting_instruction_emissions", "drafting_instruction_characters", "draft_save_attempts", "draft_created", "draft_revised",
    "draft_deduplicated", "draft_failed", "lesson_detail_overflow"} | {
    f"draft_reviewed_{value}" for value in DISPOSITIONS} | {f"draft_reason_{value}" for value in REASONS} | {
    f"{origin}_{outcome}" for origin in ("current_session", "historical_mining", "maintenance") for outcome in ("changed", "noop")}


def safe_counts(values):
    if not isinstance(values, dict):
        return {}
    return {name: amount for name, amount in values.items() if name in ACTIVITY_COUNTERS
            and isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0}


def safe_lessons(e, values):
    if not isinstance(values, dict):
        return {}
    return {name: amount for name, amount in values.items() if isinstance(name, str) and len(name) <= 128 and ":" in name
            and name.split(":", 1)[0] in e.AUTHORITIES and e.ID_PATTERN.fullmatch(name.split(":", 1)[1])
            and isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0}


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def home_path(home):
    return Path(home).expanduser().resolve() if home is not None else Path.home()


def staging(e, root, home=None):
    return e.store_path(root, authority="local", home_dir=home) / "staging"


def read_json(path, *, limit=MAX_ACTIVITY_BYTES):
    if path.stat().st_size > limit:
        raise ValueError("record exceeds size limit")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("record must be an object")
    return value


def configuration(e, root, home=None):
    root, home = Path(root).resolve(), home_path(home)
    values = dict(e.DEFAULT_CONFIG)
    sources = {key: "built-in" for key in values}
    issues = []
    paths = [home / ".agents/session-learning/config.json",
             e.store_path(root) / "config.json", e.store_path(root) / "config.local.json"]
    private = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            record = read_json(path, limit=65536)
            if record.get("schema_version") != e.CONFIG_SCHEMA_VERSION:
                raise ValueError("unsupported configuration schema")
        except (OSError, ValueError) as exc:
            issues.append({"path": str(path), "error": str(exc)})
            continue
        if path == paths[-1]:
            private = record
        for key in values:
            if key == "drafting_enabled" or key not in record:
                continue
            values[key], sources[key] = record[key], str(path)
    # A machine-owned enrollment prevents a accidentally committed personal
    # file from granting capture consent to another clone/user. It is created
    # only by explicit project configuration, and survives off/on manual edits.
    consent = False
    if private.get("drafting_enabled") is True:
        try:
            owner = read_json(staging(e, root, home) / "configuration-owner.json")
            consent = (isinstance(private.get("configuration_owner"), str)
                       and private["configuration_owner"] == owner.get("id"))
        except (OSError, ValueError):
            pass
        if not consent:
            issues.append({"path": str(paths[-1]),
                           "error": "project capture consent absent; run configure --drafting on"})
    elif "drafting_enabled" in private and not isinstance(private["drafting_enabled"], bool):
        issues.append({"path": str(paths[-1]), "error": "drafting_enabled must be boolean"})
    values["drafting_enabled"] = consent
    sources["drafting_enabled"] = str(paths[-1]) if consent else "disabled"
    for key in ("retrieval_enabled", "activity_audit_enabled"):
        if not isinstance(values[key], bool):
            issues.append({"path": sources[key], "error": f"{key} must be boolean"})
            values[key] = e.DEFAULT_CONFIG[key]
    for key in ("cooldown_user_prompts", "max_lessons_per_event", "max_context_characters"):
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append({"path": sources[key], "error": f"{key} must be a nonnegative integer"})
            values[key] = e.DEFAULT_CONFIG[key]
    executable = values.get("python_path")
    if not isinstance(executable, str) or not Path(executable).is_absolute() or not Path(executable).is_file():
        values["python_path"] = None
    return {"effective": values, "sources": sources, "paths": [str(p) for p in paths],
            "issues": issues, "automatic_exposure": "requires functioning plugin hooks; installation alone is not proof"}


def git(root, *args):
    return subprocess.run(["git", "-c", f"safe.directory={root}", "-C", str(root), *args],
                          capture_output=True, text=True, timeout=5, check=False)


def exclude_private(root):
    if not (root / ".git").exists():
        return
    tracked = git(root, "ls-files", "--", ".session-learning/config.local.json")
    if tracked.returncode or tracked.stdout.strip():
        raise ValueError("personal project configuration must be untracked")
    result = git(root, "rev-parse", "--git-path", "info/exclude")
    if result.returncode:
        raise ValueError("cannot resolve repository-local exclusion")
    path = Path(result.stdout.strip())
    if not path.is_absolute():
        path = root / path
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    rule = "/.session-learning/config.local.json"
    if rule not in content.splitlines():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n" + rule + "\n", encoding="utf-8")
    ignored = git(root, "check-ignore", "--", ".session-learning/config.local.json")
    if ignored.returncode:
        raise ValueError("personal project configuration is not excluded from Git")


def configure(e, root, *, home=None, scope="project", drafting=None, audit=None):
    root, home = Path(root).resolve(), home_path(home)
    if scope == "user" and drafting is not None:
        raise ValueError("drafting consent requires individual project configuration")
    if drafting is None and audit is None:
        return configuration(e, root, home)
    path = (home / ".agents/session-learning/config.json" if scope == "user"
            else e.store_path(root) / "config.local.json")
    with e.writer_lock(root, authority="local"):
        value = read_json(path, limit=65536) if path.exists() else {"schema_version": e.CONFIG_SCHEMA_VERSION}
        if value.get("schema_version") != e.CONFIG_SCHEMA_VERSION:
            raise ValueError("unsupported configuration schema; preserve and repair the file")
        if scope == "project":
            exclude_private(root)
            owner_path = staging(e, root, home) / "configuration-owner.json"
            owner = read_json(owner_path) if owner_path.exists() else {"id": uuid.uuid4().hex}
            e._atomic_write_bytes(owner_path, e._json_bytes(owner))
            value["configuration_owner"] = owner["id"]
        if drafting is not None:
            value["drafting_enabled"] = drafting
        if audit is not None:
            value["activity_audit_enabled"] = audit
        e._atomic_write_bytes(path, e._json_bytes(value))
    report = configuration(e, root, home)
    report["changed_file"] = str(path)
    return report


def data_path(e, root, home=None, data_dir=None):
    # Explicit host data directory wins. CLI uses host environment when present.
    selected = data_dir or os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(selected).expanduser().resolve() if selected else staging(e, root, home) / "activity"


def activity_file(e, root, data, date=None):
    return data / f"activity-{e.project_key(root)}-{date or datetime.now(timezone.utc).date().isoformat()}.json"


def add_activity(e, root, counts, *, home=None, data_dir=None, lessons=None, finalize=False, date=None):
    try:
        if not finalize and not configuration(e, root, home)["effective"]["activity_audit_enabled"]:
            return
        data = data_path(e, root, home, data_dir)
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=89)).isoformat()
        if date is not None:
            datetime.fromisoformat(date)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or date < cutoff or date > datetime.now(timezone.utc).date().isoformat():
                return
        path = activity_file(e, root, data, date)
        with e._state_lock(path, timeout_seconds=0.5):
            value = read_json(path) if path.exists() else {"schema_version": 1, "counts": {}, "lessons": {}}
            value["counts"] = safe_counts(value["counts"])
            value["lessons"] = safe_lessons(e, value["lessons"])
            for name, amount in safe_counts(counts).items():
                value["counts"][name] = value["counts"].get(name, 0) + int(amount)
            for identity, amount in safe_lessons(e, lessons or {}).items():
                if identity in value["lessons"] or len(value["lessons"]) < e.MAX_RETRIEVAL_ENTRIES * 2:
                    value["lessons"][identity] = value["lessons"].get(identity, 0) + int(amount)
                else:
                    value["counts"]["lesson_detail_overflow"] = value["counts"].get("lesson_detail_overflow", 0) + amount
            if len(e._json_bytes(value)) <= MAX_ACTIVITY_BYTES:
                e._atomic_write_bytes(path, e._json_bytes(value))
        for old in data.glob(f"activity-{e.project_key(root)}-????-??-??.json"):
            if old.name[-15:-5] < cutoff:
                old.unlink(missing_ok=True)
    except Exception:
        # Measurement must not affect capture/retrieval/canonical authoring.
        pass


def finish_hook(e, root, home, data_dir, state, result, payload, *, host):
    config = e._load_config(Path(root), home_path(home))
    event = payload.get("hook_event_name")
    enabled = config["drafting_enabled"]
    previous = state.get("drafting_exposed", False)
    pointer = None
    boundary = event == "SessionStart" and payload.get("source") in {"startup", "fork", "clear", "compact", "resume"}
    if enabled and (boundary or not previous) and event in {"SessionStart", "UserPromptSubmit"}:
        script = Path(e.__file__).resolve()
        home_option = f' --home-dir "{home_path(home)}"' if home_path(home) != Path.home() else ""
        pointer = ("Session Learning drafting is enabled for this project. At a meaningful correction, "
                   "non-obvious recovery, or useful verified discovery, load drafting guidance once per "
                   f'context with Python 3.10+: "{script}" draft-context --root "{root}"{home_option}. '
                   "Capture only compact evidence-backed observations; continue the primary task.")
    elif previous and not enabled and event != "SessionEnd":
        pointer = "Session Learning automatic drafting is now disabled; stop automatic drafting. Lesson retrieval remains available."
    pointer_emitted = False
    lesson_characters = len(result.get("hookSpecificOutput", {}).get("additionalContext", ""))
    if pointer:
        output = result.setdefault("hookSpecificOutput", {"hookEventName": event, "additionalContext": ""})
        existing = output.get("additionalContext", "")
        combined = existing + ("\n\n" if existing else "") + pointer
        if len(combined) <= config["max_context_characters"]:
            output["additionalContext"] = combined
            state["drafting_exposed"] = enabled
            pointer_emitted = True
        elif not existing:
            result.pop("hookSpecificOutput", None)
    # Audit only emitted context, using the already-written session state.
    identities = state.pop("event_lesson_emissions", [])
    if config["activity_audit_enabled"]:
        today = datetime.now(timezone.utc).date().isoformat()
        if state.get("activity_date") not in {None, today}:
            flush_hook(e, root, home, data_dir, state)
        state["activity_date"] = today
        counts = Counter(safe_counts(state.get("activity_counts", {})))
        counts["hook_events"] += 1
        text = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        if text:
            counts["context_emissions"] += 1
            counts["context_characters"] += len(text)
        if pointer_emitted:
            counts["drafting_pointer_emissions" if enabled else "drafting_revocations"] += 1
            counts["drafting_pointer_characters" if enabled else "drafting_revocation_characters"] += len(pointer)
        counts["lesson_emissions"] += len(identities)
        if identities:
            counts["lesson_characters"] += lesson_characters
        per_lesson = Counter(safe_lessons(e, state.get("activity_lessons", {})))
        for identity, amount in Counter(identities).items():
            if safe_lessons(e, {identity: amount}) and (identity in per_lesson or len(per_lesson) < e.MAX_RETRIEVAL_ENTRIES * 2):
                per_lesson[identity] += amount
            else:
                counts["lesson_detail_overflow"] += amount
        state["activity_counts"] = dict(counts)
        state["activity_lessons"] = dict(per_lesson)
        state["activity_host"] = host
    else:
        # Close previously observed counters without counting disabled events.
        flush_hook(e, root, home, data_dir, state)
    return result


def flush_hook(e, root, home, data_dir, state):
    counts = state.pop("activity_counts", {})
    lessons = state.pop("activity_lessons", {})
    date = state.pop("activity_date", None)
    if counts:
        # Already-authorized counters may be finalized after audit is disabled.
        add_activity(e, root, counts, home=home, data_dir=data_dir, lessons=lessons, finalize=True, date=date)


def _sanitize(e, value, root, home):
    if isinstance(value, str):
        value = value.replace(str(Path(root).resolve()), "<project>").replace(str(home_path(home)), "<home>")
        if len(value) > e.MAX_RECOVERY_TEXT_CHARS or e._recovery_privacy_error(value, project_root=Path(root), home_dir=home_path(home)):
            raise ValueError("draft text must be bounded, normalized, and redacted")
        return value
    if isinstance(value, list):
        if len(value) > 20:
            raise ValueError("draft lists may contain at most 20 items")
        return [_sanitize(e, item, root, home) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize(e, item, root, home) for key, item in value.items()}
    raise ValueError("draft content must contain text, lists, or objects")


def normalize_draft(e, root, value, home):
    required = {"target_authority", "source", "signal", "observation", "proposed_guidance", "verification_gaps"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("draft requires exactly target_authority, source, signal, observation, proposed_guidance, verification_gaps")
    if value["target_authority"] not in e.AUTHORITIES or value["signal"] not in e.SIGNALS - {"recovery_pair"}:
        raise ValueError("invalid draft authority or signal")
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"host", "session_id", "event_ids"}:
        raise ValueError("source requires host, session_id, event_ids")
    if source["host"] not in {"codex", "claude"} or not isinstance(source["event_ids"], list) or not 1 <= len(source["event_ids"]) <= 20:
        raise ValueError("source must identify a supported host and bounded event references")
    if any(not isinstance(item, str) or not e.RECOVERY_ID_PATTERN.fullmatch(item)
           for item in [source["session_id"], *source["event_ids"]]):
        raise ValueError("source references must be opaque bounded IDs")
    observation = value["observation"]
    fields = {"situation", "attempted_behavior", "feedback", "corrected_behavior", "outcome"}
    if not isinstance(observation, dict) or set(observation) != fields or any(not isinstance(v, str) or not v.strip() for v in observation.values()):
        raise ValueError("observation requires the five non-empty contrast fields; mark unverified outcomes explicitly")
    proposed = value["proposed_guidance"]
    if not isinstance(proposed, dict) or set(proposed) != {"statement", "scope", "triggers", "safe_path", "exceptions"}:
        raise ValueError("proposed_guidance requires statement, scope, triggers, safe_path, exceptions")
    if not isinstance(proposed["statement"], str) or not proposed["statement"].strip():
        raise ValueError("proposed statement must be non-empty")
    scope = proposed["scope"]
    if not isinstance(scope, dict) or set(scope) != {"type", "paths"} or scope["type"] not in {"repository", "paths", "subsystem"} or not isinstance(scope["paths"], list):
        raise ValueError("invalid proposed scope")
    for path in scope["paths"]:
        if not isinstance(path, str) or e._validate_relative_path(Path(root), path, "scope"):
            raise ValueError("scope paths must stay within the project")
    for field in ("triggers", "safe_path", "exceptions"):
        items = proposed[field]
        if not isinstance(items, list) or any(not isinstance(v, str) or not v.strip() for v in items):
            raise ValueError(f"{field} must contain text items")
    if not proposed["triggers"] or not proposed["safe_path"]:
        raise ValueError("proposed triggers and safe path must be clear")
    if not isinstance(value["verification_gaps"], list) or any(not isinstance(v, str) or not v.strip() for v in value["verification_gaps"]):
        raise ValueError("verification_gaps must be a text list")
    result = copy.deepcopy(value)
    for field in ("observation", "proposed_guidance", "verification_gaps"):
        result[field] = _sanitize(e, result[field], root, home)
    if len(e._json_bytes(result)) > MAX_DRAFT_BYTES - 1024:
        raise ValueError("draft exceeds size limit")
    return result


def drafts(e, root, home=None):
    directory = staging(e, root, home) / "drafts"
    result, issues = [], []
    for path in sorted(directory.glob("draft.*.json")):
        try:
            value = read_json(path, limit=MAX_DRAFT_BYTES)
            fields = {"target_authority", "source", "signal", "observation", "proposed_guidance", "verification_gaps"}
            metadata = {"schema_version", "record_type", "id", "content_fingerprint", "created_at", "updated_at", "disposition", "review_reason", "accepted"}
            if set(value) != fields | metadata or value.get("schema_version") != 1 or value.get("record_type") != "draft" or value.get("disposition") not in DISPOSITIONS or value.get("id") != path.stem:
                raise ValueError("invalid draft schema or identity")
            original = {key: value[key] for key in fields}
            normalized = normalize_draft(e, root, original, home)
            if normalized != original or value["content_fingerprint"] != fingerprint({key: item for key, item in original.items() if key != "source"}):
                raise ValueError("draft content must be normalized with a matching fingerprint")
            if value["review_reason"] is not None and value["review_reason"] not in REASONS:
                raise ValueError("invalid draft review reason")
            accepted = value["accepted"]
            if value["disposition"] == "accepted":
                if not isinstance(accepted, dict) or set(accepted) != {"authority", "operation_id", "resulting_ids"} or accepted["authority"] != value["target_authority"]:
                    raise ValueError("invalid draft acceptance metadata")
                receipt_path(e, root, accepted["authority"], accepted["operation_id"], home)
                if not isinstance(accepted["resulting_ids"], list) or any(not isinstance(item, str) or not e.ID_PATTERN.fullmatch(item) for item in accepted["resulting_ids"]):
                    raise ValueError("invalid accepted canonical IDs")
            elif accepted is not None:
                raise ValueError("reviewable/dismissed drafts cannot contain acceptance metadata")
            for key in ("created_at", "updated_at"):
                if datetime.fromisoformat(value[key]).tzinfo is None:
                    raise ValueError("draft timestamps require timezone information")
            result.append(value)
        except (OSError, ValueError, KeyError) as exc:
            issues.append({"file": path.name, "error": str(exc)})
    return result, issues


def pending(e, root, *, home=None, page=1):
    if page < 1:
        raise ValueError("page must be positive")
    records, issues = drafts(e, root, home)
    reviewable = sorted((v for v in records if v["disposition"] in REVIEWABLE), key=lambda v: (v["created_at"], v["id"]))
    selected = reviewable[(page - 1) * 20:page * 20]
    return {"total": len(reviewable), "page": page, "page_size": 20,
            "next_page": page + 1 if page * 20 < len(reviewable) else None,
            "issues": issues, "items": [{**v, "expected_sha256": e.canonical_record_sha256(v),
                "age_days": max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(v["created_at"])).days)} for v in selected]}


def draft_context(e, root, *, home=None, data_dir=None):
    if not e._load_config(Path(root), home_path(home))["drafting_enabled"]:
        return {"enabled": False}
    path = Path(e.__file__).parent.parent / "references/drafting.md"
    instructions = path.read_text(encoding="utf-8")
    add_activity(e, root, {"drafting_instruction_emissions": 1, "drafting_instruction_characters": len(instructions)}, home=home, data_dir=data_dir)
    return {"enabled": True, "instructions": instructions}


def save_draft(e, root, value, *, home=None, data_dir=None, draft_id=None, expected_sha256=None):
    if not e._load_config(Path(root), home_path(home))["drafting_enabled"]:
        return {"saved": False, "reason": "disabled"}
    add_activity(e, root, {"draft_save_attempts": 1}, home=home, data_dir=data_dir)
    value = normalize_draft(e, root, value, home)
    directory = staging(e, root, home)
    # Source event identity is separate from interpretation and content dedupe.
    content = {key: v for key, v in value.items() if key != "source"}
    content_fingerprint = fingerprint(content)
    identity = draft_id or "draft." + fingerprint(value["source"])[:24]
    if not e.ID_PATTERN.fullmatch(identity) or not identity.startswith("draft.") or len(identity) > 100:
        raise ValueError("invalid draft ID")
    path = e._within_root(directory, directory / "drafts" / (identity + ".json"))
    with e.writer_lock(root, authority="local"):
        # Configure uses this same lock: consent may have changed while this
        # save waited for another writer. Never commit using an earlier grant.
        if not e._load_config(Path(root), home_path(home))["drafting_enabled"]:
            return {"saved": False, "reason": "disabled"}
        existing, issues = drafts(e, root, home)
        if issues:
            raise ValueError("repair invalid staging records before capture")
        old = read_json(path, limit=MAX_DRAFT_BYTES) if path.exists() else None
        duplicate = next((v for v in existing if v["content_fingerprint"] == content_fingerprint), None)
        if duplicate:
            add_activity(e, root, {"draft_deduplicated": 1}, home=home, data_dir=data_dir)
            return {"saved": False, "reason": "duplicate", "id": duplicate["id"], "disposition": duplicate["disposition"]}
        if old and e.canonical_record_sha256(old) != expected_sha256:
            raise ValueError("stale draft revision")
        if old and old["disposition"] in REVIEWABLE:
            for operation_path in (directory / "acceptance").glob("accept.*.json"):
                prepared = read_json(operation_path)
                if prepared.get("draft_id") == identity and prepared.get("draft_sha256") == e.canonical_record_sha256(old):
                    raise ValueError("draft has a prepared acceptance; recover it before revision")
        if expected_sha256 and old is None:
            raise ValueError("draft revision target is missing")
        result = {**value, "schema_version": 1, "record_type": "draft", "id": identity,
                  "content_fingerprint": content_fingerprint, "created_at": old["created_at"] if old else now(),
                  "updated_at": now(), "disposition": "pending", "review_reason": None, "accepted": None}
        e._atomic_write_bytes(path, e._json_bytes(result))
        count = sum(v["disposition"] in REVIEWABLE for v in existing) + (0 if old and old["disposition"] in REVIEWABLE else 1)
        warning_path = directory / "backlog-warning.json"
        warned = warning_path.exists() and read_json(warning_path).get("warned") is True
        warning = count >= 50 and not warned
        if warning or count < 50 and warned:
            e._atomic_write_bytes(warning_path, e._json_bytes({"warned": count >= 50}))
    add_activity(e, root, {"draft_revised" if old else "draft_created": 1}, home=home, data_dir=data_dir)
    return {"saved": True, "id": identity, "expected_sha256": e.canonical_record_sha256(result),
            "reviewable": count, "warning": "50 or more drafts await explicit review" if warning else None}


def review_draft(e, root, draft_id, expected, disposition, reason, *, home=None, data_dir=None, accepted=None):
    if disposition not in DISPOSITIONS - {"pending"} or reason not in REASONS:
        raise ValueError("invalid review disposition or reason")
    directory = staging(e, root, home)
    if not e.ID_PATTERN.fullmatch(draft_id):
        raise ValueError("invalid draft ID")
    path = e._within_root(directory, directory / "drafts" / (draft_id + ".json"))
    with e.writer_lock(root, authority="local"):
        value = read_json(path, limit=MAX_DRAFT_BYTES)
        if e.canonical_record_sha256(value) != expected:
            raise ValueError("stale draft review")
        if value["disposition"] not in REVIEWABLE:
            raise ValueError("terminal draft must be revised before another review")
        if disposition != "accepted":
            for operation_path in (directory / "acceptance").glob("accept.*.json"):
                prepared = read_json(operation_path)
                if prepared.get("draft_id") == draft_id and prepared.get("draft_sha256") == expected:
                    raise ValueError("prepared acceptance must be recovered or canceled before review")
        if disposition == "accepted" and accepted is None:
            raise ValueError("accepted disposition requires a confirmed canonical operation receipt")
        if disposition == "accepted":
            receipt = read_receipt(e, receipt_path(e, root, accepted["authority"], accepted["operation_id"], home))
            operation = "accept." + hashlib.sha256((draft_id + expected).encode()).hexdigest()[:24]
            if accepted["operation_id"] != operation:
                raise ValueError("acceptance receipt belongs to a different draft revision")
            if receipt["resulting_ids"] != accepted["resulting_ids"] or accepted["authority"] != value["target_authority"]:
                raise ValueError("acceptance receipt does not identify this draft destination")
        value.update(disposition=disposition, review_reason=reason, accepted=accepted, updated_at=now())
        if len(e._json_bytes(value)) > MAX_DRAFT_BYTES:
            raise ValueError("reviewed draft exceeds record size limit")
        e._atomic_write_bytes(path, e._json_bytes(value))
        records, _ = drafts(e, root, home)
        if sum(v["disposition"] in REVIEWABLE for v in records) < 50:
            warning = directory / "backlog-warning.json"
            if warning.exists() and read_json(warning).get("warned"):
                e._atomic_write_bytes(warning, e._json_bytes({"warned": False}))
    add_activity(e, root, {f"draft_reviewed_{disposition}": 1, f"draft_reason_{reason}": 1}, home=home, data_dir=data_dir)
    return {"id": draft_id, "disposition": disposition, "reason": reason}


def accept_draft(e, root, draft_id, expected, manifest, *, home=None, data_dir=None, reason="useful_new"):
    if reason not in {"useful_new", "useful_refinement", "confirmation"}:
        raise ValueError("acceptance requires a useful review reason")
    directory = staging(e, root, home)
    if not e.ID_PATTERN.fullmatch(draft_id):
        raise ValueError("invalid draft ID")
    path = e._within_root(directory, directory / "drafts" / (draft_id + ".json"))
    with e.writer_lock(root, authority="local"):
        value = read_json(path, limit=MAX_DRAFT_BYTES)
        if e.canonical_record_sha256(value) != expected or value["disposition"] not in REVIEWABLE:
            raise ValueError("stale or terminal draft acceptance")
        if not isinstance(manifest, dict) or manifest.get("origin") != "current_session" or not manifest.get("changes"):
            raise ValueError("draft acceptance requires a nonempty current-session manifest")
        operation = "accept." + hashlib.sha256((draft_id + expected).encode()).hexdigest()[:24]
        prepared = {"manifest": {**manifest, "manifest_schema_version": 3, "operation_id": operation},
                    "draft_id": draft_id, "draft_sha256": expected, "authority": value["target_authority"], "reason": reason}
        # Never persist a raw projected instruction file in local staging.
        if any("content" in entry or "delete" in entry for entry in manifest["changes"]):
            raise ValueError("acceptance handoffs accept canonical records only; projections are engine-managed")
        validate_handoff(e, root, manifest, home)
        ids = sorted({Path(entry["path"]).stem for entry in manifest["changes"]})
        accepted_size = {**value, "disposition": "accepted", "review_reason": reason,
                         "accepted": {"authority": value["target_authority"], "operation_id": operation, "resulting_ids": ids}}
        if len(e._json_bytes(accepted_size)) > MAX_DRAFT_BYTES:
            raise ValueError("acceptance results would exceed bounded draft metadata")
        prepared_path = directory / "acceptance" / (operation + ".json")
        if prepared_path.exists() and read_json(prepared_path) != prepared:
            raise ValueError("acceptance operation changed; preserve the pending handoff")
        e._atomic_write_bytes(prepared_path, e._json_bytes(prepared))
    return complete_acceptance(e, root, prepared, home=home, data_dir=data_dir)


def validate_handoff(e, root, manifest, home):
    """Persist only canonical, bounded, sanitized manifest payloads in staging."""
    if set(manifest) - {"manifest_schema_version", "origin", "changes", "operation_id", "expected_store_revision"} or manifest.get("manifest_schema_version") not in {2, 3}:
        raise ValueError("handoff requires a supported canonical manifest without extra fields")
    if not isinstance(manifest["changes"], list):
        raise ValueError("handoff changes must be a list")
    revision = manifest.get("expected_store_revision")
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision)):
        raise ValueError("invalid handoff revision guard")
    if len(e._json_bytes(manifest)) > 65536:
        raise ValueError("acceptance manifest exceeds staging limit")
    prose_fields = {"title", "statement", "situation", "attempted_behavior", "feedback", "corrected_behavior",
                    "outcome", "anti_pattern", "safe_path", "exceptions", "triggers", "trap", "expected", "rationale"}
    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in prose_fields:
                    if _sanitize(e, item, root, home) != item:
                        raise ValueError("handoff prose must already use normalized placeholders")
                elif key == "operations":
                    for operation in item:
                        if operation.get("op") in {"replace_statement", "append_triggers", "append_exception", "replace_anti_pattern", "replace_safe_path"}:
                            if _sanitize(e, operation["value"], root, home) != operation["value"]:
                                raise ValueError("handoff patch must already be normalized")
                        check(operation)
                elif key in {"id", "session_id", "evidence_id", "lesson_id"}:
                    if not isinstance(item, str) or not e.RECOVERY_ID_PATTERN.fullmatch(item):
                        raise ValueError("handoff identities must be bounded opaque IDs")
                else:
                    check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, str):
            if _sanitize(e, value, root, home) != value:
                raise ValueError("handoff strings must already be normalized")
    for entry in manifest["changes"]:
        if not isinstance(entry, dict) or set(entry) - {"path", "json", "lesson_patch", "evidence_patch"} or len(set(entry) & {"json", "lesson_patch", "evidence_patch"}) != 1:
            raise ValueError("handoff changes require exactly one canonical payload")
        path = entry.get("path", "")
        if not isinstance(path, str) or not re.fullmatch(r"\.session-learning/(lessons|evidence|cases)/[a-z0-9][a-z0-9._-]*\.json", path):
            raise ValueError("handoff paths must identify canonical records")
        record = entry.get("json")
        if isinstance(record, dict):
            allowed = {"lesson": {"schema_version", "record_type", "id", "authority", "equivalence_key", "conflict_targets", "conflict_history", "title", "statement", "kind", "status", "scope", "triggers", "anti_pattern", "safe_path", "exceptions", "delivery", "provenance", "relationships", "usage", "timestamps", "version"},
                       "evidence": {"schema_version", "record_type", "id", "authority", "session_id", "signal", "situation", "attempted_behavior", "feedback", "corrected_behavior", "outcome", "created_at", "source", "behavior_delta"},
                       "case": {"schema_version", "record_type", "id", "lesson_ids", "situation", "trap", "expected", "created_at"}}
            if record.get("record_type") not in allowed or set(record) - allowed[record["record_type"]]:
                raise ValueError("handoff contains unsupported record fields")
            if record.get("record_type") == "evidence" and ("source" in record or "behavior_delta" in record or record.get("signal") == "recovery_pair"):
                raise ValueError("draft handoffs accept current-session evidence without historical source payloads")
            shapes = {"scope": {"type", "paths"}, "delivery": {"mode", "host", "path", "instruction_path", "enforcement_target"},
                      "relationships": {"supersedes", "related"}, "timestamps": {"created_at", "updated_at"},
                      "usage": e.USAGE_COUNTERS | e.USAGE_TIMESTAMPS}
            for field, keys in shapes.items():
                if field in record and (not isinstance(record[field], dict) or set(record[field]) - keys):
                    raise ValueError("handoff contains unsupported nested record fields")
            for item in record.get("provenance", []):
                if not isinstance(item, dict) or set(item) != {"evidence_id", "signal"}:
                    raise ValueError("handoff provenance must contain evidence identity and signal only")
            kind = record["record_type"]
            if kind == "lesson":
                # Preparation validates fields; managed projections do not exist
                # until the destination transaction creates them. Full surface
                # validation still runs before that transaction can commit.
                errors = e._validate_current_lesson_record({**record, "schema_version": e.LESSON_SCHEMA_VERSION, "version": e.SKILL_VERSION}, Path(entry["path"]), Path(root), check_projections=False)
            elif kind == "evidence":
                errors = e._validate_evidence_record(record, Path(entry["path"]), project_root=Path(root), home_dir=home_path(home))
            else:
                errors = e._validate_case_record(record, Path(entry["path"]))
            if errors:
                raise ValueError("handoff record fails canonical validation: " + "; ".join(errors[:3])[:1200])
        patch = entry.get("lesson_patch")
        if patch is not None:
            if not isinstance(patch, dict) or set(patch) - {"expected_sha256", "intent", "operations", "usage_update", "equivalence_update"}:
                raise ValueError("invalid handoff lesson patch fields")
            if not isinstance(patch.get("operations"), list):
                raise ValueError("handoff patch operations must be a list")
            for operation in patch["operations"]:
                if not isinstance(operation, dict) or set(operation) - {"op", "value"} or operation.get("op") not in e.LESSON_OPERATION_ORDER:
                    raise ValueError("invalid handoff operation fields")
            if "usage_update" in patch and (not isinstance(patch["usage_update"], dict) or set(patch["usage_update"]) - (e.USAGE_COUNTERS | e.USAGE_TIMESTAMPS)):
                raise ValueError("unsupported usage payload in handoff")
            if "equivalence_update" in patch and (not isinstance(patch["equivalence_update"], dict) or set(patch["equivalence_update"]) != {"value", "rationale"}):
                raise ValueError("unsupported equivalence payload in handoff")
        check(entry)


def complete_acceptance(e, root, prepared, *, home=None, data_dir=None):
    operation = prepared["manifest"]["operation_id"]
    receipt_path(e, root, prepared["authority"], operation, home)
    directory = staging(e, root, home) / "acceptance"
    with e.writer_lock(directory, authority="local"):
        if not (directory / (operation + ".json")).exists():
            raise ValueError("prepared acceptance was canceled")
        return _complete_acceptance(e, root, prepared, home=home, data_dir=data_dir)


def cancel_acceptance(e, root, operation, *, home=None, data_dir=None):
    directory = staging(e, root, home) / "acceptance"
    receipt_path(e, root, "project", operation, home)
    with e.writer_lock(directory, authority="local"), e.writer_lock(root, authority="local"):
        path = directory / (operation + ".json")
        prepared = read_json(path)
        if receipt_path(e, root, prepared["authority"], operation, home).exists():
            raise ValueError("canonical acceptance already committed; recover instead")
        path.unlink()
    return {"operation_id": operation, "canceled": True, "draft_id": prepared["draft_id"]}


def _complete_acceptance(e, root, prepared, *, home=None, data_dir=None):
    if not isinstance(prepared.get("draft_id"), str) or not re.fullmatch(r"draft\.[a-z0-9._-]{1,94}", prepared["draft_id"]):
        raise ValueError("invalid prepared draft identity")
    if prepared.get("authority") not in e.AUTHORITIES:
        raise ValueError("invalid prepared destination authority")
    operation = prepared["manifest"]["operation_id"]
    receipt = receipt_path(e, root, prepared["authority"], operation, home)
    draft_path = staging(e, root, home) / "drafts" / (prepared["draft_id"] + ".json")
    if not receipt.exists() and e.canonical_record_sha256(read_json(draft_path)) != prepared["draft_sha256"]:
        raise ValueError("stale prepared draft; inspect acceptance before publishing")
    result = e.apply_manifest(root, prepared["manifest"], authority=prepared["authority"], home_dir=home)
    confirmed = read_receipt(e, receipt)
    if confirmed.get("manifest_fingerprint") != manifest_fingerprint(e, prepared["manifest"]):
        raise ValueError("canonical acceptance receipt does not match the operation")
    accepted = {"authority": prepared["authority"], "operation_id": operation,
                "resulting_ids": confirmed["resulting_ids"]}
    path = staging(e, root, home) / "drafts" / (prepared["draft_id"] + ".json")
    current = read_json(path, limit=MAX_DRAFT_BYTES)
    if current.get("accepted") == accepted:
        return {"id": prepared["draft_id"], "disposition": "accepted", "canonical": result}
    review = review_draft(e, root, prepared["draft_id"], prepared["draft_sha256"], "accepted", prepared["reason"],
                         home=home, data_dir=data_dir, accepted=accepted)
    return {**review, "canonical": result}


def recover_acceptance(e, root, *, home=None, data_dir=None):
    outcomes = []
    for path in sorted((staging(e, root, home) / "acceptance").glob("accept.*.json")):
        try:
            prepared = read_json(path)
            draft = read_json(staging(e, root, home) / "drafts" / (prepared["draft_id"] + ".json"))
            if draft.get("accepted", {}) and draft["accepted"].get("operation_id") == prepared["manifest"]["operation_id"]:
                continue
            outcomes.append(complete_acceptance(e, root, prepared, home=home, data_dir=data_dir))
        except (OSError, ValueError, KeyError) as exc:
            outcomes.append({"operation": path.stem, "deferred": True, "error": str(exc)})
    return {"operations": outcomes}


def manifest_fingerprint(e, manifest):
    return fingerprint({key: value for key, value in manifest.items() if key != "operation_id"})


def receipt_path(e, root, authority, operation, home=None):
    if not isinstance(operation, str) or len(operation) > 100 or not e.ID_PATTERN.fullmatch(operation):
        raise ValueError("operation_id must be a bounded opaque identifier")
    store = e.store_path(root, authority=authority, home_dir=home)
    return e._within_root(store, store / "receipts" / (operation + ".json"))


def read_receipt(e, path):
    value = read_json(path, limit=65536)
    if set(value) != {"schema_version", "operation_id", "manifest_fingerprint", "resulting_ids"} or value["schema_version"] != 1:
        raise ValueError("invalid acceptance receipt schema")
    if value["operation_id"] != path.stem or not e.ID_PATTERN.fullmatch(value["operation_id"]):
        raise ValueError("invalid receipt identity")
    if not isinstance(value["manifest_fingerprint"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["manifest_fingerprint"]):
        raise ValueError("invalid receipt manifest fingerprint")
    ids = value["resulting_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 2000 or any(not isinstance(item, str) or not e.ID_PATTERN.fullmatch(item) for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("invalid receipt resulting IDs")
    return value


def receipt_errors(e, root, authority, home=None):
    errors = []
    for path in sorted((e.store_path(root, authority=authority, home_dir=home) / "receipts").glob("*.json")):
        try:
            read_receipt(e, path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f"receipt {path.name}: {exc}")
    return errors


def store_revision(e, root, authority, home=None):
    root = Path(root).resolve()
    store = e.store_path(root, authority=authority, home_dir=home)
    paths = [path for directory in ("lessons", "evidence", "cases") for path in sorted((store / directory).glob("*.json"))]
    # Personal guidance also depends on applicable project instructions, even
    # though local authority can never project into those files.
    surfaces = {root / "AGENTS.md", root / "CLAUDE.md"}
    lessons, _ = e._load_records(e.store_path(root), "lessons")
    for lesson in lessons:
        delivery = lesson.get("delivery")
        if not isinstance(delivery, dict):
            continue
        for key in ("path", "instruction_path"):
            location = delivery.get(key)
            if isinstance(location, str):
                try:
                    surfaces.add(e._within_root(root, root / location))
                except (OSError, ValueError):
                    pass  # Structural audit reports unsafe projection metadata.
    values = [("canonical:" + path.relative_to(store).as_posix(),
               hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None) for path in paths]
    values.extend(("surface:" + path.relative_to(root).as_posix(),
                   hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None) for path in sorted(surfaces))
    return e.canonical_record_sha256(values)


def reflection_context(e, root, *, home=None, authority="both", page=1, limit=20, query="", expected=None):
    if page < 1 or not 1 <= limit <= 20:
        raise ValueError("reflection page must be positive and limit must be 1..20")
    authorities = ("project", "local") if authority == "both" else (authority,)
    if any(v not in e.AUTHORITIES for v in authorities):
        raise ValueError("invalid reflection authority")
    if page > 1 and expected is None:
        raise ValueError("subsequent reflection pages require the original revisions")
    revisions = {name: store_revision(e, root, name, home) for name in authorities}
    if expected is not None and expected != revisions:
        raise ValueError("reflection coverage invalidated: canonical revision changed")
    health = e.audit_store(root, authority=authority, home_dir=home)
    errors = health["load_errors"] + health["validation_errors"]
    health = {"can_author": not errors, "error_count": len(errors), "errors": errors[:20],
              "errors_truncated": len(errors) > 20, "migration_count": len(health["migration_candidates"])}
    if errors:
        return {"revisions": revisions, "health": health, "items": [], "total": 0,
                "page": page, "page_size": limit, "next_page": None, "coverage": "invalid store; inspect structural audit"}
    records = []
    for name in authorities:
        loaded, _ = e._load_records(e.store_path(root, authority=name, home_dir=home), "lessons")
        for raw in loaded:
            public = e._public_record(raw)
            lesson = e.upgrade_lesson_record(public, authority=name)
            if query and not (e._tokens(query) & e._tokens([lesson["title"], lesson["statement"],
                    *lesson["scope"]["paths"], *lesson["triggers"], *lesson["safe_path"], *lesson["exceptions"]])):
                continue
            usage = lesson.get("usage", {})
            priority = (0 if lesson["status"] == "conflicted" else 1 if usage.get("repeat_corrections", 0) or usage.get("violations", 0)
                        else 2 if lesson["status"] == "candidate" else 3 if lesson["status"] == "active" else 4)
            summary = {"id": lesson["id"], "authority": name, "status": lesson["status"],
                "statement": lesson["statement"], "scope": lesson["scope"], "triggers": lesson["triggers"],
                "safe_path": lesson["safe_path"], "exceptions": lesson["exceptions"], "delivery": lesson["delivery"],
                "evidence_ids": [v["evidence_id"] for v in lesson["provenance"]], "usage": usage,
                "expected_sha256": e.canonical_record_sha256(public), "priority": priority}
            truncated = []
            def bound(value, field):
                if isinstance(value, str) and len(value) > 500:
                    truncated.append(field)
                    return value[:500]
                if isinstance(value, list):
                    if len(value) > 20:
                        truncated.append(field)
                    return [bound(item, field) for item in value[:20]]
                if isinstance(value, dict):
                    return {key: bound(item, field) for key, item in value.items()}
                return value
            for field in ("statement", "scope", "triggers", "safe_path", "exceptions", "delivery", "evidence_ids"):
                summary[field] = bound(summary[field], field)
            summary["truncated_fields"] = sorted(set(truncated))
            records.append(summary)
    records.sort(key=lambda v: (v["priority"], v["authority"], v["id"]))
    # Catch concurrent changes during the read as well as between pages.
    if revisions != {name: store_revision(e, root, name, home) for name in authorities}:
        raise ValueError("reflection coverage invalidated during read")
    return {"revisions": revisions, "total": len(records), "page": page, "page_size": limit,
            "next_page": page + 1 if page * limit < len(records) else None,
            "items": records[(page - 1) * limit:page * limit], "health": health,
            "coverage": "canonical lessons and evidence; no draft codification or history mining"}


def activity(e, root, *, home=None, data_dir=None, lesson_page=1):
    if lesson_page < 1:
        raise ValueError("lesson page must be positive")
    counts, lessons, issues = Counter(), Counter(), []
    directories = {data_path(e, root, home, data_dir), staging(e, root, home) / "activity"}
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=89)).isoformat()
    live = 0
    for directory in directories:
        for path in sorted(directory.glob(f"activity-{e.project_key(root)}-????-??-??.json")):
            if path.name[-15:-5] < cutoff:
                continue
            try:
                value = read_json(path)
                counts.update(safe_counts(value["counts"]))
                lessons.update(safe_lessons(e, value["lessons"]))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                issues.append({"file": path.name, "error": str(exc)})
        for path in sorted(directory.glob(f"state-{e._project_hash(Path(root))}-*.json")):
            try:
                value = read_json(path)
                if datetime.fromisoformat(value["updated_at"]) < datetime.now(timezone.utc) - timedelta(days=90):
                    continue
                counts.update(safe_counts(value.get("activity_counts", {})))
                lessons.update(safe_lessons(e, value.get("activity_lessons", {})))
                live += 1
            except (OSError, ValueError, KeyError, TypeError) as exc:
                issues.append({"file": path.name, "error": str(exc)})
    records, draft_issues = drafts(e, root, home)
    detail = sorted(lessons.items(), key=lambda item: (-item[1], item[0]))
    reviewable = sorted((v for v in records if v["disposition"] in REVIEWABLE), key=lambda v: v["created_at"])
    return {"counts": dict(sorted(counts.items())), "lesson_emissions": dict(detail[(lesson_page - 1) * 20:lesson_page * 20]),
            "lesson_page": lesson_page, "total_lesson_identities": len(detail),
            "next_lesson_page": lesson_page + 1 if lesson_page * 20 < len(detail) else None,
            "oldest_reviewable": [{"id": v["id"], "created_at": v["created_at"],
                "age_days": max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(v["created_at"])).days)} for v in reviewable[:5]],
            "draft_dispositions": dict(Counter(v["disposition"] for v in records)),
            "draft_review_reasons": dict(Counter(v["review_reason"] for v in records if v["review_reason"])),
            "reviewable_drafts": sum(v["disposition"] in REVIEWABLE for v in records),
            "retention_days": 90, "live_sessions": live, "issues": issues + draft_issues,
            "coverage": "observed engine emissions only; concurrent live counters are provisional; unobserved hosts, missing sessions, application, and helpfulness are unknown"}


def add_parsers(subparsers):
    for name in ("configure", "draft-context", "save-draft", "pending-drafts", "review-draft", "accept-draft",
                 "recover-acceptance", "cancel-acceptance", "activity", "reflection-context"):
        parser = subparsers.add_parser(name)
        parser.add_argument("--root")
        parser.add_argument("--home-dir")
        parser.add_argument("--data-dir")
        if name == "configure":
            parser.add_argument("--scope", choices=("project", "user"), default="project")
            parser.add_argument("--drafting", choices=("on", "off"))
            parser.add_argument("--audit", choices=("on", "off"))
        if name in {"save-draft", "accept-draft"}:
            parser.add_argument("input", help="JSON file or - for standard input")
        if name in {"save-draft", "accept-draft", "review-draft"}:
            parser.add_argument("--draft-id", required=name != "save-draft")
            parser.add_argument("--expected-sha256", required=name != "save-draft")
        if name == "review-draft":
            parser.add_argument("--disposition", choices=("deferred", "dismissed"), required=True)
            parser.add_argument("--reason", choices=sorted(REASONS), required=True)
        if name == "accept-draft":
            parser.add_argument("--reason", choices=("useful_new", "useful_refinement", "confirmation"), default="useful_new")
        if name == "cancel-acceptance":
            parser.add_argument("--operation-id", required=True)
        if name == "activity":
            parser.add_argument("--lesson-page", type=int, default=1)
        if name in {"pending-drafts", "reflection-context"}:
            parser.add_argument("--page", type=int, default=1)
        if name == "reflection-context":
            parser.add_argument("--authority", choices=("project", "local", "both"), default="both")
            parser.add_argument("--query", default="")
            parser.add_argument("--expect-revisions", help="JSON object from the first page")
    return {"configure", "draft-context", "save-draft", "pending-drafts", "review-draft", "accept-draft",
            "recover-acceptance", "cancel-acceptance", "activity", "reflection-context"}


def dispatch(e, args, root):
    shared = {"home": args.home_dir, "data_dir": args.data_dir}
    if args.command == "configure":
        return configure(e, root, home=args.home_dir, scope=args.scope,
                         drafting=None if args.drafting is None else args.drafting == "on",
                         audit=None if args.audit is None else args.audit == "on")
    if args.command == "pending-drafts":
        return pending(e, root, home=args.home_dir, page=args.page)
    if args.command == "reflection-context":
        return reflection_context(e, root, home=args.home_dir, authority=args.authority, page=args.page, query=args.query,
                                  expected=json.loads(args.expect_revisions) if args.expect_revisions else None)
    if args.command in {"save-draft", "accept-draft"}:
        if args.command == "save-draft" and not e._load_config(Path(root), home_path(args.home_dir))["drafting_enabled"]:
            return {"saved": False, "reason": "disabled"}
        import sys
        text = sys.stdin.read(MAX_ACTIVITY_BYTES + 1) if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        if len(text.encode()) > MAX_ACTIVITY_BYTES:
            raise ValueError("input exceeds size limit")
        value = json.loads(text.lstrip("\ufeff"))
        if args.command == "save-draft":
            return save_draft(e, root, value, draft_id=args.draft_id, expected_sha256=args.expected_sha256, **shared)
        return accept_draft(e, root, args.draft_id, args.expected_sha256, value, reason=args.reason, **shared)
    if args.command == "review-draft":
        return review_draft(e, root, args.draft_id, args.expected_sha256, args.disposition, args.reason, **shared)
    if args.command == "cancel-acceptance":
        return cancel_acceptance(e, root, args.operation_id, **shared)
    if args.command == "activity":
        return activity(e, root, lesson_page=args.lesson_page, **shared)
    return {"draft-context": draft_context, "recover-acceptance": recover_acceptance}[args.command](e, root, **shared)
