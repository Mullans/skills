"""Run portable research infrastructure fixtures against distributed source assets."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parent
assets = root.parents[1]/'plugins/mullans-engineering/skills/maintain-research-docs/assets/research-system'
sys.path.insert(0, str(assets))
sys.path.insert(0, str(assets/'scripts/workspace'))
suite = unittest.defaultTestLoader.discover(str(root), pattern='test_*.py')
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
