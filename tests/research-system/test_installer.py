"""Setup installer guards and runnable fresh-project infrastructure."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILLS = Path(__file__).resolve().parents[2]/'plugins/mullans-engineering/skills'
SETUP = SKILLS/'research-setup'
spec = importlib.util.spec_from_file_location('pipeline_install', SETUP/'scripts/install_research_pipeline.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        self.root.mkdir()

    def test_install_and_rerun_preserve_existing_bytes(self):
        initial = installer.install(self.root, SETUP)
        self.assertEqual(11, len(initial['created']))
        marker = self.root/'docs/wiki.md'
        marker.write_bytes(b'custom adopted policy\n')
        again = installer.install(self.root, SETUP)
        self.assertEqual([], again['created'])
        self.assertTrue(again['adoption_review_required'])
        self.assertEqual(b'custom adopted policy\n', marker.read_bytes())

    def test_dry_run_and_check_do_not_write(self):
        self.assertEqual(11, len(installer.install(self.root, SETUP, dry_run=True)['created']))
        self.assertFalse(installer.install(self.root, SETUP, check=True)['ok'])
        self.assertEqual([], list(self.root.iterdir()))

    def test_missing_sibling_preflight_leaves_project_empty(self):
        incomplete = Path(self.temp.name)/'skills/research-setup'
        incomplete.mkdir(parents=True)
        (incomplete/'SKILL.md').write_text('setup')
        with self.assertRaises(ValueError):
            installer.install(self.root, incomplete)
        self.assertEqual([], list(self.root.iterdir()))

    def test_fresh_core_and_installed_commands(self):
        # Setup adapts the core templates before the non-overwriting installer.
        (self.root/'docs/research').mkdir(parents=True)
        (self.root/'experiments').mkdir()
        shutil.copyfile(SETUP/'assets/investigation.md', self.root/'experiments/TEMPLATE.md')
        shutil.copyfile(SETUP/'assets/findings.md', self.root/'docs/research/README.md')
        shutil.copyfile(SETUP/'assets/project-guide.md', self.root/'docs/README.md')
        (self.root/'next-handoff.md').write_text('# Current work\n')
        installer.install(self.root, SETUP)
        for command in [
            ['research_catalog.py', 'check'], ['research_docs.py', 'audit'],
            ['check_doc_links.py']
        ]:
            run = subprocess.run([sys.executable, str(self.root/'scripts/workspace'/command[0]), *command[1:]],
                                 cwd=self.root, capture_output=True, text=True)
            self.assertEqual(0, run.returncode, run.stdout + run.stderr)

if __name__ == '__main__':
    unittest.main()
