from pathlib import Path
import json
import shutil
import tempfile
import unittest

from scripts.workspace import research_catalog as catalog, research_docs as docs

SEEDS = Path(__file__).resolve().parents[2]/'plugins/mullans-engineering/skills/maintain-research-docs/assets/research-system/docs/research/catalog'


class PortableSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(SEEDS, self.root/'docs/research/catalog')
        (self.root/'experiments').mkdir()
        registry, _ = docs.load(self.root)
        for page in registry['pages']:
            path = self.root/page['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# Setup document\n', encoding='utf-8')

    def test_fresh_project_has_complete_empty_catalog_and_clean_audit(self):
        config = catalog.load_config(self.root)
        index = catalog.refresh(config, self.root)
        self.assertTrue(index['coverage']['complete'])
        self.assertEqual([], index['findings'])
        self.assertEqual([], index['metadata_issues'])
        audit = docs.audit(self.root)
        self.assertTrue(audit['complete'])
        self.assertEqual(0, audit['review_count'])

    def test_templates_do_not_become_findings(self):
        # An unfenced example is deliberately malformed as a finding. It must
        # remain searchable documentation rather than fail technical metadata.
        path = self.root/'docs/research/reference-template.md'
        path.write_text('# Shape\n## Finding PROJECT-EXAMPLE-001: Example\nexampletext\n', encoding='utf-8')
        index = catalog.refresh(catalog.load_config(self.root), self.root)
        self.assertEqual([], index['findings'])
        self.assertEqual([], index['metadata_issues'])
        self.assertGreater(catalog.search(index, 'exampletext')['total_matches'], 0)

    def test_configuration_and_subjects_can_live_outside_index_roots(self):
        config = catalog.load_config(self.root)
        config.pop('fingerprint')
        config['include_roots'] = ['experiments']
        custom = self.root/'config/research.json'
        custom.parent.mkdir()
        custom.write_text(json.dumps(config), encoding='utf-8')
        loaded = catalog.load_config(self.root, 'config/research.json')
        index = catalog.refresh(loaded, self.root)
        self.assertTrue(index['coverage']['complete'])
        self.assertEqual([], index['metadata_issues'])
        self.assertEqual([], index['documents'])
        with self.assertRaises(ValueError):
            catalog.load_config(self.root, '../outside.json')

    def test_retained_setup_roles_do_not_mask_new_subjects(self):
        (self.root/'docs/research/new-subject.md').write_text('# New subject\n', encoding='utf-8')
        audit = docs.audit(self.root)
        row = next(r for r in audit['pages'] if r['path'].endswith('new-subject.md'))
        self.assertEqual(['unclassified'], row['reasons'])
        self.assertEqual(1, audit['review_count'])
