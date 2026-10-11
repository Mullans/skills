"""Offline batch-review, Git-baseline and Markdown guarantees."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.workspace import research_docs as docs
from scripts.workspace import research_markdown as md
from scripts.workspace import check_doc_links


class MarkdownTests(unittest.TestCase):
    def test_units_and_fences(self):
        text = '# Topic\n```markdown\n### Finding PROJECT-FAKE-001: fake\n```\n### Contract PROJECT-X-001: Layout\n| a | b |\n#### Detail\nvalue\n### Negative result PROJECT-X-002: Failed\nresult\n'
        found = md.units(text)
        self.assertEqual(['PROJECT-X-001', 'PROJECT-X-002'], [u['id'] for u in found])
        self.assertIn('#### Detail', found[0]['text'])

    def test_reference_forms_and_anchors(self):
        text = '# A `field`\n## Repeat\n## Repeat\n[x][a] [a] [a][] [inline](other.md#repeat)\n[a]: other.md#repeat\n'
        self.assertEqual(4, sum(not c.definition for c in md.citations(text)))
        self.assertEqual({'a-field', 'repeat', 'repeat-1'}, md.anchors(text))
        self.assertIn('[x](other.md#repeat)', md.expand_references('[x][a]', text))
        self.assertEqual(['[x][missing]'], md.unresolved_references('[x][missing]'))

    def test_projection_and_technical_punctuation(self):
        a = '# Title\n**Value:** `owner+1BC` | 0x1234 | <=\n[x](old.md)\n```cpp\nx=3;\n```\n**Review basis:** date\nsha256=old\n**Limits:** Ground only.\n'
        b = a.replace('(old.md)', '(new.md)').replace('sha256=old', 'sha256=new')
        self.assertEqual(md.projection(a, True), md.projection(b, True))
        self.assertNotIn('x=3;', md.projection(a))
        self.assertIn('x=3;', md.projection(a, True))
        self.assertIn('owner+1BC', md.projection(a))
        self.assertIn('<=', md.projection(a))
        technical = '`__fastcall a | b`\n```cpp\nflags=a|b; ptr**=value; [label](literal);\n```\n'
        comparison = md.projection(technical, True)
        self.assertIn('__fastcall a | b', comparison)
        self.assertIn('flags=a|b; ptr**=value; [label](literal);', comparison)

    def test_link_checker_and_reference_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'docs').mkdir()
            old = root/'docs/old.md'; old.write_text('# Contract\n', encoding='utf-8')
            citing = root/'docs/use.md'; citing.write_text('[1]\n\n[1]: old.md#contract\n', encoding='utf-8')
            self.assertEqual((1, []), check_doc_links.check({citing}, root))
            old.rename(root/'docs/new.md')
            citing.write_text(citing.read_text().replace('old.md', 'new.md'), encoding='utf-8')
            self.assertIn('new.md#contract', citing.read_text())
            citing.write_text('[1]\n\n[1]: new.md#missing\n', encoding='utf-8')
            self.assertEqual(1, len(check_doc_links.check({citing}, root)[1]))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        docs.git(self.root, 'init', '-b', 'main')
        docs.git(self.root, 'config', 'user.name', 'Fixture')
        docs.git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        docs.git(self.root, 'config', 'core.autocrlf', 'false')
        self.path = 'docs/research/reference.md'
        self.write('experiments/evidence.md', '# Verified\nScoped observation.\n')
        self.write(self.path, self.reference())
        self.registry = {'schema_version': 1, 'measurement_version': 1, 'defaults': deepcopy(docs.DEFAULTS),
                         'pages': [{'id': 'reference', 'path': self.path, 'role': 'subject',
                                    'rationale': 'Reference fixture', 'onboarded': True}], 'retired': []}
        self.save_registry(); self.commit('initial')

    def reference(self, words=0):
        return '# Reference\n### Contract PROJECT-TEST-CONTRACT-001: Fields\nVerified `owner+1BC`. [1](../../experiments/evidence.md#verified)\n'+('word '*words).rstrip()+'\n'

    def write(self, path, text):
        file = self.root/path; file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8'); return file

    def save_registry(self):
        self.write(docs.REGISTRY, json.dumps(self.registry, indent=2)+'\n')

    def commit(self, title):
        docs.git(self.root, 'add', '--all'); docs.git(self.root, 'commit', '-m', title)
        return docs.git(self.root, 'rev-parse', 'HEAD').decode().strip()

    def proposal(self):
        path = 'experiments/review/proposal.json'
        bundle = docs.propose(self.root, path, [self.path])
        item = bundle['items'][0]
        item.update({'approval': 'approved', 'rationale': 'One coherent contract',
                     'citation_support': 'accepted', 'technical_evidence': 'unchanged', 'unresolved': []})
        self.write(path, json.dumps(bundle)+'\n')
        return path, bundle

    def test_percent_replacement_and_accumulation(self):
        change = docs.changed(self.root, 'a b c d e', 'a b C D e')
        self.assertEqual((2, 2, 40), (change['added_words'], change['removed_words'], change['percent']))
        self.assertTrue(docs.changed(self.root, '', 'one')['empty_baseline'])
        self.assertEqual(100, docs.changed(self.root, '', 'one')['percent'])
        self.assertEqual(0, docs.changed(self.root, '**a** [b](one.md)', 'a [b](two.md)')['percent'])

    def test_threshold_boundaries_and_overrides(self):
        words = docs.metrics(self.reference())['words']
        self.registry['defaults']['word_threshold'] = words; self.save_registry()
        self.assertEqual(0, docs.audit(self.root)['review_count'])
        self.registry['pages'][0]['overrides'] = {'unit_threshold': 0}; self.save_registry()
        self.assertEqual(1, docs.audit(self.root)['review_count'])

    def test_retained_growth_requires_current_size(self):
        path, _ = self.proposal(); self.assertTrue(docs.finalize(self.root, path)['ok'])
        self.registry, _ = docs.load(self.root)
        self.registry['defaults']['word_threshold'] = 2000; self.save_registry()
        self.write(self.path, self.reference(100))
        self.assertEqual(0, docs.audit(self.root)['review_count'])
        self.registry['defaults']['word_threshold'] = 5; self.save_registry()
        self.assertEqual(1, docs.audit(self.root)['review_count'])

    def test_batch_finalize_idempotent_and_latest_doc_commit(self):
        baseline = docs.git(self.root, 'rev-parse', 'HEAD').decode().strip()
        self.write('unrelated.txt', 'later'); self.commit('unrelated')
        path, _ = self.proposal()
        preview = docs.finalize(self.root, path, True)
        self.assertTrue(preview['ok']); self.assertFalse((self.root/'local').exists())
        self.assertTrue(docs.finalize(self.root, path)['changed'])
        self.assertFalse(docs.finalize(self.root, path)['changed'])
        registry, _ = docs.load(self.root)
        self.assertEqual(baseline, registry['pages'][0]['baseline']['commit'])

    def test_uncommitted_and_index_mismatch_reject_entire_batch(self):
        path, _ = self.proposal(); before = (self.root/docs.REGISTRY).read_bytes()
        self.write(self.path, self.reference(1))
        result = docs.finalize(self.root, path)
        self.assertFalse(result['ok']); self.assertEqual(before, (self.root/docs.REGISTRY).read_bytes())
        self.write(self.path, self.reference()); docs.git(self.root, 'add', self.path)
        self.write(self.path, self.reference(3)); docs.git(self.root, 'add', self.path)
        self.write(self.path, self.reference())
        self.assertFalse(docs.finalize(self.root, path)['ok'])

    def test_pending_rejected_do_not_reset(self):
        path, bundle = self.proposal(); bundle['items'][0]['approval'] = 'rejected'
        self.write(path, json.dumps(bundle))
        self.assertEqual([], docs.finalize(self.root, path)['updated'])
        registry, _ = docs.load(self.root); self.assertNotIn('baseline', registry['pages'][0])

    def test_stale_source_and_changed_patch(self):
        _, bundle = self.proposal(); docs.validate_sources(self.root, bundle)
        self.write(self.path, self.reference(2))
        with self.assertRaisesRegex(ValueError, 'stale'): docs.validate_sources(self.root, bundle)

    def test_changed_patch_and_nested_units(self):
        path, bundle = self.proposal()
        patch_file = self.write('experiments/review/change.patch', 'original patch')
        bundle['items'][0]['patches'] = [{'path': 'experiments/review/change.patch', 'sha256': docs.digest(patch_file.read_bytes())}]
        patch_file.write_text('different patch')
        self.write(path, json.dumps(bundle))
        with self.assertRaisesRegex(ValueError, 'patch changed'): docs.validate_sources(self.root, bundle)
        self.assertFalse(docs.finalize(self.root, path)['ok'])
        nested = self.reference()+'#### Contract PROJECT-NESTED-001: Nested\n[1](../../experiments/evidence.md)\n'
        self.assertTrue(any('nested' in issue for issue in docs.lint(self.root, self.path, nested)))

    def test_mixed_batch_failure_leaves_entire_registry(self):
        path, bundle = self.proposal()
        second = deepcopy(bundle['items'][0]); second['id'] = 'second'
        second['outputs'][0]['path'] = 'docs/research/missing.md'
        pending = deepcopy(second); pending['id'] = 'pending'; pending['approval'] = 'pending'
        bundle['items'].extend([second, pending]); self.write(path, json.dumps(bundle))
        before = (self.root/docs.REGISTRY).read_bytes()
        self.assertFalse(docs.finalize(self.root, path)['ok'])
        self.assertEqual(before, (self.root/docs.REGISTRY).read_bytes())

    def test_support_and_head_changes_block_publication(self):
        path, bundle = self.proposal()
        source = 'experiments/evidence.md'
        bundle['items'][0]['sources'].append({'path': source, 'sha256': docs.digest((self.root/source).read_bytes())})
        self.write(path, json.dumps(bundle)); self.write(source, '# Verified\nChanged support.\n')
        with self.assertRaisesRegex(ValueError, 'support changed'): docs.finalize(self.root, path)
        self.write(source, '# Verified\nScoped observation.\n')
        original_git = docs.git
        def moving_head(root, *args, **kwargs):
            if args == ('rev-parse', 'HEAD') and (self.root/'local/research-doc-maintenance/finalize.lock').exists():
                return b'0'*40+b'\n'
            return original_git(root, *args, **kwargs)
        with patch.object(docs, 'git', side_effect=moving_head):
            with self.assertRaisesRegex(ValueError, 'HEAD changed'): docs.finalize(self.root, path)
        registry, _ = docs.load(self.root); self.assertNotIn('baseline', registry['pages'][0])

    def test_lock_not_taken_over(self):
        path, _ = self.proposal(); lock = self.write('local/research-doc-maintenance/finalize.lock', 'other')
        with self.assertRaisesRegex(ValueError, 'lock held'): docs.finalize(self.root, path)
        self.assertEqual('other', lock.read_text())

    def test_registry_concurrency_and_atomic_failure(self):
        path, _ = self.proposal(); original = docs.read
        def conflict(file):
            value = original(file)
            if file == self.root/docs.REGISTRY and (self.root/'local/research-doc-maintenance/finalize.lock').exists():
                return value+b' '
            return value
        with patch.object(docs, 'read', side_effect=conflict):
            with self.assertRaisesRegex(ValueError, 'registry changed'): docs.finalize(self.root, path)
        before = (self.root/docs.REGISTRY).read_bytes()
        with patch.object(docs.os, 'replace', side_effect=OSError('publication fixture')):
            with self.assertRaises(OSError): docs.finalize(self.root, path)
        self.assertEqual(before, (self.root/docs.REGISTRY).read_bytes())
        self.assertFalse(list((self.root/docs.REGISTRY).parent.glob('*.tmp')))

    def test_missing_baseline_and_measurement_version(self):
        path, _ = self.proposal(); docs.finalize(self.root, path)
        registry, _ = docs.load(self.root); self.registry = registry
        self.registry['pages'][0]['baseline']['measurement_version'] = 0; self.save_registry()
        self.assertIn('measurement-version', docs.audit(self.root)['pages'][0]['reasons'])
        self.registry['pages'][0]['baseline']['commit'] = '0'*40; self.save_registry()
        self.assertFalse(docs.audit(self.root)['complete'])

    def test_duplicate_units_and_legacy_classification(self):
        self.write(self.path, self.reference()+self.reference())
        self.assertTrue(any(e.get('issue') == 'duplicate unit ID' for e in docs.audit(self.root)['errors']))
        self.registry['pages'][0]['onboarded'] = False; self.save_registry()
        self.assertIn('legacy-onboarding', docs.audit(self.root)['pages'][0]['reasons'])
        self.write('docs/research/new.md', '# New\n')
        self.assertTrue(any('unclassified' in r['reasons'] for r in docs.audit(self.root)['pages']))

    def test_isolated_commit_preserves_unrelated_index(self):
        path, bundle = self.proposal()
        self.write('other.txt', 'staged other'); docs.git(self.root, 'add', 'other.txt')
        before = docs.git(self.root, 'show', ':other.txt')
        self.write(self.path, self.reference(4))
        bundle['items'][0]['outputs'][0]['sha256'] = docs.digest((self.root/self.path).read_bytes())
        self.write(path, json.dumps(bundle))
        revision = docs.commit_batch(self.root, path, 'approved reference')
        self.assertEqual(before, docs.git(self.root, 'show', ':other.txt'))
        self.assertEqual(self.path, docs.git(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', revision).decode().strip())
        self.assertTrue(docs.finalize(self.root, path)['ok'])

    def test_overlapping_staged_changes_block(self):
        path, _ = self.proposal(); self.write(self.path, self.reference(1)); docs.git(self.root, 'add', self.path)
        self.write(self.path, self.reference())
        with self.assertRaisesRegex(ValueError, 'overlap'): docs.commit_batch(self.root, path, 'blocked')

    def test_rename_and_retirement(self):
        path, bundle = self.proposal()
        moved = 'docs/research/renamed.md'
        (self.root/self.path).rename(self.root/moved); self.commit('renamed')
        item = bundle['items'][0]
        item['action'] = 'split'; item['retire'] = ['reference']
        item['deleted_paths'] = [self.path]
        item['outputs'][0].update({'path': moved, 'id': 'new-reference'})
        self.write(path, json.dumps(bundle))
        self.assertTrue(docs.finalize(self.root, path)['ok'])
        registry, _ = docs.load(self.root)
        self.assertEqual('reference', registry['retired'][0]['id'])
        self.assertEqual(moved, registry['pages'][0]['path'])
        repeated = docs.finalize(self.root, path)
        self.assertTrue(repeated['ok']); self.assertFalse(repeated['changed'])

    def test_merge_latest_document_commit(self):
        docs.git(self.root, 'checkout', '-b', 'branch')
        self.write(self.path, self.reference(2)); self.commit('document branch')
        docs.git(self.root, 'checkout', 'main'); self.write('parallel.txt', 'parallel'); self.commit('parallel')
        docs.git(self.root, 'merge', '--no-ff', 'branch', '-m', 'merge')
        path, _ = self.proposal()
        self.assertTrue(docs.finalize(self.root, path)['ok'])


if __name__ == '__main__': unittest.main()
