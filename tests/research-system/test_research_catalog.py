"""Offline retrieval guarantees; no game or profile access."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("research_catalog", Path(__file__).resolve().parents[2] / "plugins/mullans-engineering/skills/maintain-research-docs/assets/research-system/scripts/workspace/research_catalog.py")
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "experiments").mkdir()
        self.cfg = {"include_roots": ["docs", "experiments"], "include_files": [],
                    "exclude_prefixes": ["experiments/benchmark/assets"], "candidate_roots": ["ideas"],
                    "max_section_chars": 200, "fingerprint": "fixture"}

    def note(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def refresh(self):
        return catalog.refresh(self.cfg, self.root)

    def test_unregistered_note_and_old_negative_result(self):
        self.note("experiments/old/README.md", "# Old work\n## Rejected approach\nNo replacement appeared during the observed window.")
        first = self.refresh()
        self.note("docs/untracked.md", "# New capture\nDiscriminating observation found.")
        second = self.refresh()
        self.assertEqual(1, first["coverage"]["indexed"])
        self.assertEqual(2, second["coverage"]["indexed"])
        result = catalog.search(second, "replacement observed window")
        self.assertEqual("experiments/old/README.md", result["results"][0]["path"])
        self.assertEqual("indexed; claims unreviewed", result["results"][0]["review"])
        self.assertEqual("docs/untracked.md", catalog.search(second, "discriminating")["results"][0]["path"])

    def test_content_hash_refresh_deletion_and_rename(self):
        path = self.note("docs/old.md", "# A\nalpha result")
        before = self.refresh()["documents"][0]["sha256"]
        # Same-length text changes cannot hide behind size or timestamp shortcuts.
        stamp = path.stat().st_mtime_ns
        path.write_text("# A\nomega result", encoding="utf-8")
        import os
        os.utime(path, ns=(stamp, stamp))
        index = self.refresh()
        self.assertNotEqual(before, index["documents"][0]["sha256"])
        old_locator = catalog.search(index, "omega")["results"][0]["locator"]
        path.rename(self.root / "docs/new.md")
        index = self.refresh()
        self.assertEqual("docs/new.md", index["documents"][0]["path"])
        with self.assertRaises(ValueError):
            catalog.show(index, old_locator)
        (self.root / "docs/new.md").unlink()
        self.assertEqual(0, self.refresh()["coverage"]["indexed"])

    def test_keys_fixtures_and_outside_policy(self):
        self.note("experiments/benchmark/README.md", "# Assessment\nAuthored limits.")
        self.note("experiments/benchmark/assets/key.md", "# Hidden\nsecretanswer")
        self.note("ideas/omitted.md", "# Candidate\nnot in allowed roots")
        index = self.refresh()
        self.assertEqual(0, catalog.search(index, "secretanswer")["total_matches"])
        self.assertEqual(["ideas/omitted.md"], index["coverage"]["candidate_outside_policy"])
        self.assertEqual("experiments/benchmark/assets", index["coverage"]["excluded"][0]["path"])

    def test_future_research_drafts_excluded(self):
        self.cfg['exclude_research_drafts'] = True
        self.note('experiments/future-review/drafts/reference.md', '# Copy\nproposalonly')
        self.note('experiments/future-review/README.md', '# Review\nrecommendation')
        index = self.refresh()
        self.assertEqual(0, catalog.search(index, 'proposalonly')['total_matches'])
        self.assertEqual(1, index['coverage']['indexed'])
        self.assertTrue(any(e['reason'] == 'research proposal drafts' for e in index['coverage']['excluded']))

    def test_unreadable_and_unsupported_are_visible(self):
        unreadable = self.note("docs/denied.md", "# Denied\nbody")
        (self.root / "docs/invalid.md").write_bytes(b"\xff\xfe")
        original = catalog.read_source
        def deny(path):
            if path == unreadable:
                raise PermissionError("fixture denial")
            return original(path)
        with patch.object(catalog, "read_source", side_effect=deny):
            index = self.refresh()
        self.assertFalse(index["coverage"]["complete"])
        self.assertEqual({"unreadable", "unsupported"}, {p["state"] for p in index["coverage"]["problems"]})
        self.assertEqual(2, catalog.search(index, "missing")["coverage"]["problem_count"])

    def test_large_document_is_searchable_and_retrieval_stays_bounded(self):
        self.note('docs/large.md', '# Long record\n' + 'padding text\n' * 90000
                  + '\n## Relevant result\nlargefilemarker observed.\n')
        index = self.refresh()
        self.assertTrue(index['coverage']['complete'])
        self.assertEqual(1, index['coverage']['indexed'])
        result = catalog.search(index, 'largefilemarker')
        self.assertEqual(1, result['total_matches'])
        shown = catalog.show(index, result['results'][0]['locator'])
        self.assertIn('largefilemarker', shown['text'])
        self.assertLessEqual(len(shown['text']), self.cfg['max_section_chars'])

    def test_reviewed_finding_in_large_document_keeps_source_review(self):
        self.note('docs/large.md', '# Preamble\n' + 'padding text\n' * 90000
                  + '\n' + self.finding())
        index = self.refresh()
        finding = catalog.show(index, 'PROJECT-TEST-001')
        self.assertEqual([], finding['review_warnings'])
        self.assertEqual('Controlled effect was observed.', finding['fields']['Statement'])

    def test_bounded_sections_fences_and_continuation(self):
        self.note("docs/long.md", "# Real\n```python\n# fake heading\n```\n" + "body needle\n" * 100)
        index = self.refresh()
        sections = index["documents"][0]["sections"]
        self.assertTrue(all(len(s["text"]) <= 200 for s in sections))
        self.assertTrue(all(s["heading"] == "Real" for s in sections))
        result = catalog.search(index, "needle", limit=1)
        self.assertTrue(result["truncated"])
        next_result = catalog.search(index, "needle", limit=1, offset=1)
        self.assertNotEqual(result["results"][0]["locator"], next_result["results"][0]["locator"])
        shown = catalog.show(index, result["results"][0]["locator"])
        self.assertLessEqual(len(shown["text"]), 200)
        self.assertLessEqual(len(result["results"][0]["excerpt"]), 401)

    def test_exact_tokens_do_not_conflate_addresses(self):
        self.note("docs/a.md", "# Address\n0x1234 cap=20")
        index = self.refresh()
        self.assertEqual(0, catalog.search(index, "0x123")["total_matches"])
        self.assertEqual(1, catalog.search(index, "0x1234")["total_matches"])

    def test_publication_failure_keeps_fresh_search_and_prior_generation(self):
        self.note("docs/a.md", "# A\noriginal")
        self.refresh()
        cache = self.root / catalog.CACHE_PATH
        prior = cache.read_bytes()
        self.note("docs/a.md", "# A\nnewword")
        with patch.object(catalog.os, "replace", side_effect=PermissionError("interrupted publish")):
            index = self.refresh()
        self.assertIn("fresh in-memory", index["cache_warning"])
        self.assertEqual(1, catalog.search(index, "newword")["total_matches"])
        self.assertEqual(prior, cache.read_bytes())
        self.assertEqual([], list(cache.parent.glob("*.tmp")))
        json.loads(cache.read_text(encoding="utf-8"))

    def test_discovery_failure_cannot_become_successful_empty_search(self):
        with patch.object(catalog, "discover", side_effect=OSError("enumeration failed")):
            with self.assertRaises(OSError):
                self.refresh()

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            catalog.inside(self.root, "../elsewhere")

    def finding(self, identifier="PROJECT-TEST-001"):
        evidence = "# Evidence\n## Observation\nMeasured result.\n## Unrelated\nOther text."
        self.note("experiments/evidence.md", evidence)
        sha = next(s["section_sha256"] for s in catalog.split_sections(evidence, 200) if s["anchor"] == "observation")
        return (f"# Knowledge\n## Finding {identifier}: Controlled effect\n"
                "**Statement:** Controlled effect was observed.\n"
                "**Applies under:** fixture build, private mode\n"
                "**Basis:** [Observation](../experiments/evidence.md#observation)\n"
                "**Limits and open issues:** Transfer is unknown.\n"
                f"**Review basis:** 2026-10-01; [Observation](../experiments/evidence.md#observation) sha256={sha}\n"
                "**Relationships:** Related investigation; no universal claim.\n")

    def test_finding_round_trip_and_section_review_freshness(self):
        self.note("docs/knowledge.md", self.finding())
        index = self.refresh()
        finding = catalog.show(index, "PROJECT-TEST-001")
        self.assertEqual("Controlled effect was observed.", finding["fields"]["Statement"])
        self.assertEqual([], finding["review_warnings"])
        result = catalog.search(index, "PROJECT-TEST-001")["results"][0]
        self.assertEqual("reviewed finding", result["type"])
        self.assertEqual("fixture build, private mode", result["scope"])
        self.assertIn("no universal", result["relationships"])
        # A changed unrelated section must not invalidate the observation review.
        path = self.root / "experiments/evidence.md"
        path.write_text(path.read_text().replace("Other text.", "New unrelated paragraph."))
        self.assertEqual([], self.refresh()["findings"][0]["review_warnings"])
        path.write_text(path.read_text().replace("Measured result.", "Contrary measurement."))
        self.assertIn("support section changed", self.refresh()["findings"][0]["review_warnings"][0])

    def test_duplicate_and_malformed_findings_retain_plain_text(self):
        finding = self.finding()
        self.note("docs/one.md", finding)
        self.note("docs/two.md", finding)
        self.note("docs/malformed.md", "# Findings\n## Finding PROJECT-BAD-001: Recall\nmalformedneedle")
        index = self.refresh()
        self.assertEqual([], index["findings"])
        self.assertEqual({"duplicate-finding-id", "malformed-finding"}, {i["state"] for i in index["metadata_issues"]})
        self.assertIn("docs/two.md", next(d for d in index["documents"] if d["path"] == "docs/one.md")["same_content_paths"])
        self.assertEqual(1, catalog.search(index, "malformedneedle")["total_matches"])
        with self.assertRaises(ValueError):
            catalog.show(index, "PROJECT-TEST-001")

    def test_reference_style_review_and_child_heading(self):
        text = self.finding()
        text = text.replace('[Observation](../experiments/evidence.md#measured)', '[Observation][receipt]') if '#measured)' in text else text
        # Use the fixture's actual review target, whatever its named section is.
        import re
        target = re.search(r'\[([^\]]+)\]\(([^)]+)\)\s+sha256=', text)
        self.assertIsNotNone(target)
        text = text.replace(target[0].split(' sha256=')[0], f'[{target[1]}][receipt]')
        text += '\n\n[receipt]: '+target[2]+'\n'
        text = text.replace('**Statement:**', '#### Technical detail\n\n**Statement:**')
        self.note('docs/reference.md', text)
        index = self.refresh()
        self.assertEqual(1, len(index['findings']))
        self.assertEqual([], index['findings'][0]['review_warnings'])

    def test_review_dependency_deletion_is_reported(self):
        self.note("docs/knowledge.md", self.finding())
        (self.root / "experiments/evidence.md").unlink()
        finding = self.refresh()["findings"][0]
        self.assertTrue(any("missing" in warning for warning in finding["review_warnings"]))
        self.assertTrue(any("broken evidence" in warning for warning in finding["review_warnings"]))

    def test_alias_navigation_and_malformed_subject_fallback(self):
        self.note("docs/damage.md", "# Weapon damage\nControlled scalar effect.")
        self.cfg["subjects_file"] = "subjects.json"
        subject = {"id": "damage", "name": "weapon damage", "aliases": ["hurting zombies"],
                   "entry_points": ["docs/damage.md"], "path_prefixes": [], "related": []}
        path = self.root / "subjects.json"
        path.write_text(json.dumps({"subjects": [subject]}))
        index = self.refresh()
        result = catalog.search(index, "hurting zombies")
        self.assertEqual("docs/damage.md", result["results"][0]["path"])
        self.assertEqual("damage", result["subject_navigation"][0]["id"])
        self.assertEqual("damage", catalog.search(index, "scalar", subject_filter="damage")["subject_filter"])
        with self.assertRaises(ValueError):
            catalog.search(index, "scalar", subject_filter="unknown")
        path.write_text("not json")
        index = self.refresh()
        self.assertEqual(1, catalog.search(index, "scalar")["total_matches"])
        self.assertEqual("malformed-subjects", index["metadata_issues"][0]["state"])

    def test_active_lessons_remain_workflow_guidance(self):
        self.cfg["active_lessons_root"] = "lessons"
        for status in ("active", "candidate", "superseded"):
            path = self.root / "lessons" / f"{status}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"record_type": "lesson", "status": status, "title": "Capture rule",
                                        "statement": "Inspect prior captures.", "triggers": ["repeat captures"]}))
        index = self.refresh()
        result = catalog.search(index, "captures")
        self.assertEqual(1, result["total_matches"])
        self.assertEqual("active workflow lesson", result["results"][0]["type"])
        self.assertIn("not technical corroboration", result["results"][0]["review"])

    def test_concurrent_publication_uses_isolated_temporary_files(self):
        from concurrent.futures import ThreadPoolExecutor
        cache = self.root / "cache/index.json"
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda n: catalog.publish({"generation": n}, cache), range(10)))
        self.assertIn(json.loads(cache.read_text())["generation"], range(10))
        self.assertEqual([], list(cache.parent.glob("*.tmp")))

    def test_malformed_lesson_retains_other_search_and_reports_coverage_limit(self):
        self.note("docs/a.md", "# A\nordinaryword")
        self.cfg["active_lessons_root"] = "lessons"
        folder = self.root / "lessons"
        folder.mkdir()
        (folder / "bad.json").write_text("[]")
        index = self.refresh()
        self.assertEqual(1, catalog.search(index, "ordinaryword")["total_matches"])
        self.assertFalse(index["coverage"]["complete"])
        self.assertEqual("malformed-lesson", index["metadata_issues"][0]["state"])

    def test_cli_failure_is_explicit_and_nonzero(self):
        from contextlib import redirect_stderr
        from io import StringIO
        output = StringIO()
        with patch.object(catalog.sys, "argv", ["catalog", "search", "anything"]), \
             patch.object(catalog, "load_config", side_effect=ValueError("broken configuration")), \
             redirect_stderr(output):
            self.assertEqual(2, catalog.main())
        self.assertIn("no successful zero-match conclusion", output.getvalue())


if __name__ == "__main__":
    unittest.main()
