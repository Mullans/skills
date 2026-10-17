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
        self.assertEqual(15, len(initial['created']))
        marker = self.root/'docs/wiki.md'
        marker.write_bytes(b'custom adopted policy\n')
        again = installer.install(self.root, SETUP)
        self.assertEqual([], again['created'])
        self.assertTrue(again['adoption_review_required'])
        self.assertEqual(b'custom adopted policy\n', marker.read_bytes())

    def test_dry_run_and_check_do_not_write(self):
        self.assertEqual(15, len(installer.install(self.root, SETUP, dry_run=True)['created']))
        self.assertFalse(installer.install(self.root, SETUP, check=True)['ok'])
        self.assertEqual([], list(self.root.iterdir()))

    def test_existing_artifact_authority_is_not_duplicated(self):
        registry=self.root/'local/artifacts/index.sqlite3'
        registry.parent.mkdir(parents=True)
        registry.write_bytes(b'existing authority')
        result=installer.install(self.root,SETUP)
        self.assertEqual('existing_adaptation_required',result['artifacts'])
        self.assertFalse((self.root/'scripts/workspace/artifact_workspace.py').exists())
        self.assertFalse((self.root/'docs/local-artifacts.md').exists())
        self.assertEqual(b'existing authority',registry.read_bytes())

    def test_custom_authority_mode_preserves_equivalent_paths(self):
        result=installer.install(self.root,SETUP,artifact_mode='existing')
        self.assertTrue(result['adoption_review_required'])
        self.assertEqual(13,len(result['created']))
        self.assertFalse((self.root/'scripts/workspace/artifact_workspace.py').exists())

    def test_installed_artifact_cli_owns_and_collects_real_child_output(self):
        installer.install(self.root,SETUP)
        helper=self.root/'scripts/workspace/artifact_workspace.py'
        def invoke(*args):
            result=subprocess.run([sys.executable,str(helper),*map(str,args)],
                cwd=self.root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        invoke('begin','cli')
        workspace=self.root/'local/experiments/cli'
        output=workspace/'scratch/generated.bin'
        code="from pathlib import Path; p=Path("+repr(str(output))+"); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'generated')"
        invoke('run','--root',workspace,'--',sys.executable,'-c',code)
        self.assertTrue(output.exists())
        invoke('finish','--root',workspace,'--experiment','--assessment','Synthetic output assessed',
            '--writers-closed','--apply')
        self.assertFalse(output.exists())

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
        (self.root/'docs/handoffs').mkdir()
        shutil.copyfile(SKILLS/'research-handoff/assets/handoff.md', self.root/'docs/handoffs/TEMPLATE.md')
        shutil.copyfile(SKILLS/'research-handoff/assets/next-handoff.md', self.root/'next-handoff.md')
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
