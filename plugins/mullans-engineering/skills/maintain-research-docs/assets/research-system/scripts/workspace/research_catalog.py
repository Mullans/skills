"""Discover authored working-tree research and retrieve bounded source sections.

Generated indexes are disposable. Catalog text is data, and lexical relevance is
not a review of a claim. This module deliberately has no game/runtime imports.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import unquote
from uuid import uuid4
try:
    import research_markdown as md
except ModuleNotFoundError:
    from scripts.workspace import research_markdown as md

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = "docs/research/catalog/config.json"
CACHE_PATH = "local/research-catalog/index.json"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
WORDS = re.compile(r"\w+", re.UNICODE)
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "local", "third_party", "build", "dist"}
STOPWORDS = {"a", "an", "and", "the", "of", "for", "to", "in", "with", "what", "is", "was"}
FINDING = re.compile(r"^Finding ([A-Z][A-Z0-9-]+):\s*(.+)$")
FIELD = re.compile(r"^\*\*([A-Za-z ]+):\*\*\s*", re.MULTILINE)
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")
REVIEW_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)\s+sha256=([a-f0-9]{64})")
REQUIRED_FIELDS = {"Statement", "Applies under", "Basis", "Limits and open issues", "Review basis", "Relationships"}


def fingerprint(raw):
    return hashlib.sha256(raw).hexdigest()


def inside(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes workspace: {relative}")
    return path


def load_config(root=ROOT, config_path=CONFIG_PATH):
    raw = read_source(inside(root, config_path))
    cfg = json.loads(raw.decode("utf-8-sig"))
    for key in ("include_roots", "include_files", "exclude_prefixes", "candidate_roots"):
        if not isinstance(cfg.get(key), list):
            raise ValueError(f"config {key} must be a list")
        for relative in cfg[key]:
            inside(root, relative)
    for key in ("subjects_file", "active_lessons_root"):
        if cfg.get(key):
            inside(root, cfg[key])
    if not isinstance(cfg.get('exclude_research_drafts', False), bool):
        raise ValueError('exclude_research_drafts must be boolean')
    if not 200 <= cfg["max_section_chars"] <= 10000:
        raise ValueError("max_section_chars must be 200..10000")
    cfg["fingerprint"] = fingerprint(raw)
    return cfg


def read_source(path):
    """Read internally, detecting concurrent replacement; output is bounded separately."""
    for _ in range(2):
        before = path.stat()
        with path.open("rb") as stream:
            raw = stream.read()
            opened = os.fstat(stream.fileno())
        after = path.stat()
        signature = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino)
        if signature(before) == signature(opened) == signature(after):
            return raw
    raise OSError("source changed during both read attempts")


def has_prefix(path, prefix):
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


def discover(cfg, root=ROOT):
    allowed, candidates = set(), set()
    excluded, failures = {}, []

    def walk(relative, include):
        folder = inside(root, relative)
        if not folder.exists():
            if include:
                failures.append({"path": relative, "state": "missing-root", "reason": "configured root missing"})
            return
        def error(exc):
            failures.append({"path": str(exc.filename), "state": "unreadable", "reason": "directory enumeration failed"})
        for base, dirs, files in os.walk(folder, followlinks=False, onerror=error):
            keep = []
            for name in sorted(dirs):
                path = Path(base) / name
                rel = path.relative_to(root).as_posix()
                reason = next((p for p in cfg["exclude_prefixes"] if has_prefix(rel, p)), None)
                if cfg.get('exclude_research_drafts') and rel.startswith('experiments/') and name == 'drafts':
                    reason = 'research proposal drafts'
                if name in SKIP_DIRS or path.is_symlink() or reason or not path.resolve().is_relative_to(root.resolve()):
                    excluded[rel] = {"path": rel, "state": "excluded-directory", "reason": reason or "cache/vendor/link directory"}
                else:
                    keep.append(name)
            dirs[:] = keep
            for name in sorted(files):
                if not name.lower().endswith(".md"):
                    continue
                path = Path(base) / name
                rel = path.relative_to(root).as_posix()
                reason = next((p for p in cfg["exclude_prefixes"] if has_prefix(rel, p)), None)
                if path.is_symlink() or reason or not path.resolve().is_relative_to(root.resolve()):
                    excluded[rel] = {"path": rel, "state": "excluded", "reason": reason or "external/link file"}
                elif include:
                    allowed.add(rel)
                else:
                    candidates.add(rel)

    for relative in cfg["include_roots"]:
        walk(relative, True)
    for relative in cfg["include_files"]:
        path = inside(root, relative)
        if path.is_file() and not path.is_symlink():
            allowed.add(relative)
        else:
            failures.append({"path": relative, "state": "missing-source", "reason": "configured file missing or linked"})
    for relative in cfg["candidate_roots"]:
        walk(relative, False)
    for path in root.glob("*.md"):
        if not path.is_symlink():
            candidates.add(path.relative_to(root).as_posix())
    return sorted(allowed), list(excluded.values()), sorted(candidates - allowed), failures


def split_sections(content, maximum):
    """Heading sections outside code fences, split into bounded line-aware spans."""
    sections, chain, lines = [], [], []
    start, fence = 1, None
    anchors = {}

    def flush():
        if not lines:
            return
        text = "\n".join(lines)
        section_hash = fingerprint(text.encode("utf-8"))
        anchor = slug(chain[-1]) if chain else ""
        number = anchors.get(anchor, 0)
        anchors[anchor] = number + 1
        if number:
            anchor += f"-{number}"
        offset, part = 0, 1
        while offset < len(text):
            end = min(len(text), offset + maximum)
            # Prefer a line boundary; long single lines still get bounded chunks.
            boundary = text.rfind("\n", offset, end)
            if end < len(text) and boundary > offset + maximum // 2:
                end = boundary + 1
            sections.append({"heading": " / ".join(chain) or "Preamble", "section_line": start,
                             "line": start + text[:offset].count("\n"), "part": part,
                             "text": text[offset:end], "section_sha256": section_hash, "anchor": anchor})
            offset, part = end, part + 1

    for number, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        marker = re.match(r"(`{3,}|~{3,})", stripped)
        if marker:
            char, length = marker[1][0], len(marker[1])
            if fence is None:
                fence = (char, length)
            elif char == fence[0] and length >= fence[1]:
                fence = None
            match = None
        else:
            match = HEADING.match(line) if fence is None else None
        if match:
            flush()
            chain = chain[:len(match[1]) - 1] + [match[2]]
            lines, start = [line], number
        else:
            lines.append(line)
    flush()
    return sections


def document_type(path):
    if path.startswith("docs/handoffs/") or path == "next-handoff.md":
        return "handoff/navigation"
    if path.startswith("experiments/"):
        return "investigation"
    if path.startswith("docs/references/"):
        return "reference source"
    if path.startswith(".agents/"):
        return "workflow guidance"
    if path.startswith("ideas/"):
        return "idea/proposal"
    return "authored documentation"


def slug(value):
    return re.sub(r"[^\w\- ]", "", value.casefold()).replace(" ", "-")


def local_reference(root, source, target):
    target = unquote(target.strip("<>"))
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
        return None
    relative, _, anchor = target.partition("#")
    path = (root / source).parent / relative if relative else root / source
    if not path.resolve().is_relative_to(root.resolve()):
        return None
    return path.resolve().relative_to(root.resolve()).as_posix(), anchor


def attach_findings(index, root):
    """Parse explicit reviewed fields only. Invalid records retain searchable text."""
    findings, issues = [], []
    docs = {d["path"]: d for d in index["documents"]}
    for doc in index["documents"]:
        # Templates are useful navigation but never reviewed technical findings.
        if Path(doc["path"]).name.lower() in {"template.md", "reference-template.md"}:
            continue
        groups = {}
        for section in doc["sections"]:
            # Child headings are part of their enclosing finding contract.
            finding_heading = next((h for h in reversed(section['heading'].split(' / ')) if FINDING.match(h)), None)
            if finding_heading:
                groups.setdefault(finding_heading, []).append(section)
        document_text = read_source(inside(root, doc['path'])).decode('utf-8-sig') if groups else ''
        for heading, group in groups.items():
            match = FINDING.match(heading)
            text = '\n'.join(''.join(s['text'] for s in group if s['section_line'] == line)
                             for line in dict.fromkeys(s['section_line'] for s in group))
            text = md.expand_references(text, document_text)
            fields, invalid = {}, []
            markers = list(FIELD.finditer(text))
            for i, marker in enumerate(markers):
                if marker[1] in fields:
                    invalid.append(f"duplicate field {marker[1]}")
                fields[marker[1]] = text[marker.end():markers[i + 1].start() if i + 1 < len(markers) else len(text)].strip()
            missing = REQUIRED_FIELDS - fields.keys()
            if missing:
                invalid.append("missing fields: " + ", ".join(sorted(missing)))
            if any(not fields.get(name) for name in REQUIRED_FIELDS):
                invalid.append("required fields must be nonempty")
            if len(text) > 10000 or any(len(v) > 2000 for v in fields.values()):
                invalid.append("finding fields exceed bounded display contract")
            reviews = list(REVIEW_LINK.finditer(fields.get("Review basis", "")))
            if not reviews or not re.match(r"\d{4}-\d{2}-\d{2};", fields.get("Review basis", "")):
                invalid.append("review basis requires date and section fingerprints")
            if invalid:
                issues.append({"path": doc["path"], "id": match[1], "state": "malformed-finding", "reason": "; ".join(invalid)})
                continue
            warnings, dependencies = [], []
            for review in reviews:
                parsed = local_reference(root, doc["path"], review[1])
                dependency = {"reference": review[1], "reviewed_sha256": review[2]}
                dependencies.append(dependency)
                if not parsed or not parsed[1]:
                    warnings.append("review reference needs a local indexed section: " + review[1])
                    continue
                target, anchor = parsed
                target_doc = docs.get(target)
                section = next((s for s in target_doc["sections"] if s["anchor"] == anchor), None) if target_doc else None
                dependency["current_sha256"] = section["section_sha256"] if section else None
                if section is None:
                    warnings.append("reviewed section missing or outside indexed coverage: " + review[1])
                elif section["section_sha256"] != review[2]:
                    warnings.append("support section changed; applicability review needed: " + review[1])
            for link in LINK.finditer(fields["Basis"] + "\n" + fields["Relationships"]):
                parsed = local_reference(root, doc["path"], link[1])
                if parsed:
                    target, anchor = parsed
                    if not inside(root, target).exists():
                        warnings.append("broken evidence/relationship path: " + link[1])
                    elif anchor and target in docs and not any(s["anchor"] == anchor for s in docs[target]["sections"]):
                        warnings.append("broken evidence/relationship heading: " + link[1])
            findings.append({"id": match[1], "title": match[2], "path": doc["path"],
                             "locators": [s["locator"] for s in group], "fields": fields,
                             "review_warnings": warnings, "dependencies": dependencies})
    duplicate_ids = {f["id"] for f in findings if sum(g["id"] == f["id"] for g in findings) > 1}
    for finding in findings:
        if finding["id"] in duplicate_ids:
            issues.append({"path": finding["path"], "id": finding["id"], "state": "duplicate-finding-id", "reason": "structured finding withheld"})
    index["findings"] = [f for f in findings if f["id"] not in duplicate_ids]
    index["metadata_issues"] = issues


def load_subjects(cfg, root):
    if not cfg.get("subjects_file"):
        return [], []
    try:
        data = json.loads(read_source(inside(root, cfg["subjects_file"])).decode("utf-8-sig"))
        subjects = data["subjects"]
        ids = set()
        for subject in subjects:
            if subject["id"] in ids:
                raise ValueError("duplicate subject id")
            ids.add(subject["id"])
            if not isinstance(subject["id"], str) or not isinstance(subject["name"], str):
                raise ValueError("subject id/name must be text")
            if not all(isinstance(subject[k], list) for k in ("aliases", "entry_points", "path_prefixes", "related")):
                raise ValueError("subject list field malformed")
            if any(not isinstance(v, str) for k in ("aliases", "entry_points", "path_prefixes", "related") for v in subject[k]):
                raise ValueError("subject list entries must be text")
            for path in subject["entry_points"] + subject["path_prefixes"]:
                inside(root, path)
        for subject in subjects:
            if not set(subject["related"]) <= ids:
                raise ValueError("unknown related subject")
        issues = [{"path": p, "state": "broken-subject-entry", "reason": s["id"]}
                  for s in subjects for p in s["entry_points"] if not inside(root, p).is_file()]
        return subjects, issues
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], [{"path": cfg["subjects_file"], "state": "malformed-subjects", "reason": str(exc)[:180]}]


def active_lessons(cfg, root):
    """Read only active record navigation/statement, never promote technical facts."""
    if not cfg.get("active_lessons_root"):
        return [], []
    documents, issues = [], []
    folder = inside(root, cfg["active_lessons_root"])
    if not folder.is_dir():
        return [], [{"path": cfg["active_lessons_root"], "state": "missing-lessons", "reason": "configured lesson root missing"}]
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        try:
            raw = read_source(path)
            data = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("lesson record must be an object")
            if data.get("record_type") != "lesson" or data.get("status") != "active":
                continue
            text = "\n".join([data["title"], data["statement"], "Triggers: " + "; ".join(data["triggers"])])
            sections = split_sections(text, cfg["max_section_chars"])
            for section in sections:
                section["locator"] = f"{rel}@{section['section_line']}:{section['part']}"
            documents.append({"path": rel, "title": data["title"], "sha256": fingerprint(raw), "bytes": len(raw),
                              "type": "active workflow lesson", "review": "workflow guidance; not technical corroboration",
                              "sections": sections})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            issues.append({"path": rel, "state": "malformed-lesson", "reason": str(exc)[:180]})
    return documents, issues


def build(cfg, root=ROOT):
    started = time.perf_counter()
    allowed, excluded, candidates, problems = discover(cfg, root)
    documents = []
    for relative in allowed:
        path = inside(root, relative)
        byte_length = None
        try:
            byte_length = path.stat().st_size
            raw = read_source(path)
            content = raw.decode("utf-8-sig")
            sections = split_sections(content, cfg["max_section_chars"])
            title = next((m[2] for line in content.splitlines() if (m := HEADING.match(line))), relative)
            for section in sections:
                section["locator"] = f"{relative}@{section['section_line']}:{section['part']}"
            documents.append({"path": relative, "title": title, "sha256": fingerprint(raw),
                              "bytes": len(raw), "type": document_type(relative),
                              "review": "indexed; claims unreviewed", "sections": sections})
        except (OSError, UnicodeError) as exc:
            state = "unsupported" if isinstance(exc, UnicodeError) else "unreadable"
            problems.append({"path": relative, "state": state, "type": "Markdown", "bytes": byte_length, "reason": str(exc)[:180]})
    lessons, lesson_issues = active_lessons(cfg, root)
    documents.extend(lessons)
    problems.extend(lesson_issues)
    index = {"schema": 1, "generation": uuid4().hex, "built_at": datetime.now(timezone.utc).isoformat(),
            "config_sha256": cfg["fingerprint"], "documents": documents,
            "coverage": {"eligible": len(allowed) + len(lessons) + len(lesson_issues), "indexed": len(documents), "reviewed_findings": 0,
                         "excluded": sorted(excluded, key=lambda x: x["path"]),
                         "candidate_outside_policy": candidates, "problems": problems,
                         "complete": not problems, "seconds": round(time.perf_counter() - started, 3)}}
    attach_findings(index, root)
    index["subjects"], subject_issues = load_subjects(cfg, root)
    index["metadata_issues"].extend(subject_issues + lesson_issues)
    copies = {}
    for doc in documents:
        copies.setdefault(doc["sha256"], []).append(doc["path"])
    for doc in documents:
        doc["same_content_paths"] = [p for p in copies[doc["sha256"]] if p != doc["path"]]
    index["coverage"]["reviewed_findings"] = len(index["findings"])
    index["coverage"]["seconds"] = round(time.perf_counter() - started, 3)
    return index


def publish(index, cache):
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="generation-", suffix=".tmp", dir=cache.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(index, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, cache)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def refresh(cfg, root=ROOT, cache=None):
    # Hash all eligible bounded documents each time. No timestamp-only cache hit.
    index = build(cfg, root)
    index["freshness"] = "fresh source reads; working tree is not a transaction"
    try:
        publish(index, cache or inside(root, CACHE_PATH))
    except OSError as exc:
        index["cache_warning"] = f"fresh in-memory generation used; publication failed: {type(exc).__name__}"
    return index


def terms(value):
    return [w.casefold() for w in WORDS.findall(value)]


def excerpt(text, query_terms, maximum=400):
    match = next((m for m in WORDS.finditer(text) if m[0].casefold() in query_terms), None)
    start = max(0, match.start() - 100) if match else 0
    return ("…" if start else "") + re.sub(r"\s+", " ", text[start:start + maximum])


def search(index, query, limit=8, offset=0, subject_filter=None):
    wanted = set(terms(query)) - STOPWORDS
    if not wanted:
        raise ValueError("query has no searchable terms")
    if subject_filter and not any(s["id"] == subject_filter for s in index.get("subjects", [])):
        raise ValueError("unknown subject filter")
    normalized = " " + " ".join(terms(query)) + " "
    routed = [s for s in index.get("subjects", []) if any(" " + " ".join(terms(alias)) + " " in normalized
              for alias in [s["name"], *s["aliases"]])]
    for subject in routed:
        wanted.update(set(terms(subject["name"])) - STOPWORDS)
    matches = []
    findings = {locator: f for f in index.get("findings", []) for locator in f["locators"]}
    for doc in index["documents"]:
        path_terms, title_terms = set(terms(doc["path"])), set(terms(doc["title"]))
        associated = [s["id"] for s in index.get("subjects", []) if doc["path"] in s["entry_points"]
                      or any(has_prefix(doc["path"], p) for p in s["path_prefixes"])]
        if subject_filter and subject_filter not in associated:
            continue
        for section in doc["sections"]:
            body_terms, heading_terms = set(terms(section["text"])), set(terms(section["heading"]))
            found = wanted & (body_terms | heading_terms | path_terms | title_terms)
            if not found:
                continue
            score = 10 * len(found) / len(wanted) + 3 * len(wanted & heading_terms) + 2 * len(wanted & title_terms)
            exact = query.casefold() in section["text"].casefold()
            score += 8 if exact else 0
            entry_point = any(doc["path"] in s["entry_points"] for s in routed)
            score += 12 if entry_point else 4 if set(associated) & {s["id"] for s in routed} else 0
            finding = findings.get(section["locator"])
            score += 6 if finding and entry_point else 0
            score -= 8 if len(section["text"].strip()) < 80 else 0
            matches.append({"path": doc["path"], "heading": section["heading"], "locator": section["locator"],
                            "line": section["line"], "excerpt": excerpt(section["text"], wanted),
                            "match_reason": {"terms": sorted(found), "exact_phrase": exact,
                                             "alias_routes": [s["id"] for s in routed], "entry_point": entry_point},
                            "type": "reviewed finding" if finding else doc["type"],
                            "review": "reviewed within recorded scope" if finding else doc["review"],
                            "scope": finding["fields"]["Applies under"] if finding else "not assigned",
                            "finding_id": finding["id"] if finding else None,
                            "review_warnings": finding["review_warnings"] if finding else [],
                            "relationships": finding["fields"]["Relationships"] if finding else None,
                            "basis": finding["fields"]["Basis"] if finding else None, "subjects": associated,
                            "same_content_paths": doc.get("same_content_paths", [])[:20],
                            "source_sha256": doc["sha256"], "section_sha256": section["section_sha256"],
                            "score": round(score, 3)})
    matches.sort(key=lambda x: (-x["score"], x["path"], x["line"], x["locator"]))
    selected = matches[offset:offset + limit]
    return {"generation": index["generation"], "freshness": index["freshness"],
            "cache_warning": index.get("cache_warning"), "query": query, "total_matches": len(matches),
            "subject_filter": subject_filter,
            "returned": len(selected), "offset": offset, "truncated": offset + len(selected) < len(matches),
            "coverage": coverage_summary(index), "subject_navigation": routed, "results": selected}


def coverage_summary(index):
    coverage = index["coverage"]
    return {k: coverage[k] for k in ("eligible", "indexed", "reviewed_findings", "complete", "seconds")} | {
        "problem_count": len(coverage["problems"]), "problems": coverage["problems"][:20],
        "outside_policy_count": len(coverage["candidate_outside_policy"]),
        "excluded_count": len(coverage["excluded"]),
        "metadata_issue_count": len(index.get("metadata_issues", [])),
        "metadata_issues": index.get("metadata_issues", [])[:20],
        "metadata_issues_truncated": len(index.get("metadata_issues", [])) > 20,
        "review_warning_count": sum(bool(f["review_warnings"]) for f in index.get("findings", []))}


def show(index, locator):
    finding = next((f for f in index.get("findings", []) if f["id"] == locator), None)
    if finding:
        # Structured fields point back to the canonical source; no separate claim copy.
        return {"generation": index["generation"], **finding}
    if "#" in locator:
        path, anchor = locator.split("#", 1)
        doc = next((d for d in index["documents"] if d["path"] == path), None)
        selected = [s for s in doc["sections"] if s["anchor"] == anchor] if doc else []
        if selected:
            return {"generation": index["generation"], "path": path, "source_sha256": doc["sha256"],
                    "review": doc["review"], "available_parts": len(selected),
                    "next_locator": selected[1]["locator"] if len(selected) > 1 else None, **selected[0]}
    for doc in index["documents"]:
        for section in doc["sections"]:
            if section["locator"] == locator:
                return {"generation": index["generation"], "path": doc["path"], "source_sha256": doc["sha256"],
                        "review": doc["review"], **section}
    raise ValueError("locator is unavailable in the current working tree; search again")


def regression_checks(index, cfg):
    results = []
    for case in cfg.get("regression_queries", []):
        found = search(index, case["query"], limit=8)["results"]
        selected = next((r for r in found if (case.get("expected_finding") and r["finding_id"] == case["expected_finding"])
                         or (case.get("expected_path") and r["path"] == case["expected_path"])), None)
        results.append({**case, "passed": selected is not None,
                        "locator": selected["locator"] if selected else None})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", default=CONFIG_PATH, help="Repository-relative catalog configuration")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "refresh", "check"):
        p = sub.add_parser(command)
        p.add_argument("--limit", type=int, default=20)
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--subject", help="optional reviewed subject ID; first search the full corpus")
    p.add_argument("--format", choices=("json", "text"), default="text")
    p = sub.add_parser("show")
    p.add_argument("locator")
    p.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()
    try:
        if hasattr(args, "limit") and not 1 <= args.limit <= 50:
            parser.error("limit must be 1..50")
        if getattr(args, "offset", 0) < 0:
            parser.error("offset must be nonnegative")
        root = args.root.resolve()
        cfg = load_config(root, args.config)
        index = refresh(cfg, root)
        if args.command == "search":
            result = search(index, args.query, args.limit, args.offset, args.subject)
            if args.format == "json":
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"{result['total_matches']} matches; {result['returned']} shown; truncated={result['truncated']}")
                for subject in result["subject_navigation"]:
                    print(f"Navigation: {subject['id']} -> {', '.join(subject['entry_points'])}; related: {', '.join(subject['related'])}")
                for item in result["results"]:
                    print(f"{item['locator']} {item['heading']} [{item['type']}; {item['review']}]\n  {item['excerpt']}")
                    print(f"  Match terms: {', '.join(item['match_reason']['terms'])}; scope: {item['scope']}")
                    if item["review_warnings"]:
                        print(f"  Review warnings: {item['review_warnings']}")
                    if item["relationships"]:
                        print(f"  Relationships: {item['relationships']}")
                print(json.dumps(result["coverage"], ensure_ascii=False))
                if result["cache_warning"]:
                    print(result["cache_warning"])
        elif args.command == "show":
            record = show(index, args.locator)
            if args.format == "json":
                print(json.dumps(record, ensure_ascii=False, indent=2))
            elif "fields" in record:
                print(f"{record['id']} {record['title']} — {record['path']}")
                for name, value in record["fields"].items():
                    print(f"{name}: {value}\n")
                print(f"Source locators: {', '.join(record['locators'])}")
                print(f"Review warnings: {record['review_warnings']}")
            else:
                print(f"{record['locator']} — {record['review']}\nSection SHA256: {record['section_sha256']}\n{record['text']}")
                if record.get("next_locator"):
                    print(f"Continued at {record['next_locator']}")
        else:
            report = {"generation": index["generation"], "freshness": index["freshness"],
                      "cache_warning": index.get("cache_warning"), **coverage_summary(index)}
            for key in ("excluded", "candidate_outside_policy", "problems"):
                values = index["coverage"][key]
                report[key] = values[:args.limit]
                report[key + "_truncated"] = len(values) > args.limit
            regressions = regression_checks(index, cfg) if args.command == "check" else []
            if args.command == "check":
                report["regression_checks"] = regressions
            print(json.dumps(report, ensure_ascii=False, indent=2))
            if args.command == "check" and (not index["coverage"]["complete"] or index["metadata_issues"]
                                           or any(f["review_warnings"] for f in index["findings"])
                                           or any(not r["passed"] for r in regressions)):
                return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"catalog failure: {exc}; no successful zero-match conclusion is available", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
