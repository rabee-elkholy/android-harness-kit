"""Failure injection around engine staging; no edits outside temporary fixtures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_or_update as installer


class TransactionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.repo, self.kit = root / 'repo', root / 'kit'
        for base in (self.repo / '.agents', self.kit / 'agents'):
            (base / 'scripts').mkdir(parents=True)
            (base / 'skills/android-harness/references').mkdir(parents=True)
            (base / 'state').mkdir()
        (self.repo / '.agents/VERSION').write_text('old')
        (self.repo / '.agents/state/baseline.json').write_text('{"schema_version": 2}')
        (self.repo / '.agents/state/old-pass.json').write_text('stale')
        (self.kit / 'agents/VERSION').write_text('new')
        (self.kit / 'agents/scripts/final_verdict.py').write_text('# new engine')

    def test_staging_copy_failure_preserves_old_engine(self):
        with patch.object(installer.shutil, 'copytree', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                installer.place_engine(self.repo, self.kit, {})
        self.assertEqual('old', (self.repo / '.agents/VERSION').read_text())

    def test_update_preserves_policy_and_adds_new_reference(self):
        policy = '{"version":1,"require":["ui_expert"]}'
        (self.repo / '.agents/review-policy.json').write_text(policy)
        (self.kit / 'agents/skills/android-harness/references/new-guide.md').write_text('new guide')
        installer.place_engine(self.repo, self.kit, {'custom.md': 'tailored'})
        self.assertEqual(policy, (self.repo / '.agents/review-policy.json').read_text())
        self.assertEqual('new guide', (self.repo / '.agents/skills/android-harness/references/new-guide.md').read_text())
        self.assertEqual('tailored', (self.repo / '.agents/skills/android-harness/references/custom.md').read_text())

    def test_invalid_policy_aborts_without_replacing_engine(self):
        (self.repo / '.agents/review-policy.json').write_text('{"version":1,"exclude":["test_quality"]}')
        with self.assertRaises(ValueError):
            installer.place_engine(self.repo, self.kit, {})
        self.assertEqual('old', (self.repo / '.agents/VERSION').read_text())

    def test_success_preserves_baseline_not_old_gate_results(self):
        installer.place_engine(self.repo, self.kit, {'custom.md': 'my conventions'})
        self.assertEqual('new', (self.repo / '.agents/VERSION').read_text())
        self.assertTrue((self.repo / '.agents/state/baseline.json').exists())
        self.assertFalse((self.repo / '.agents/state/old-pass.json').exists())
        self.assertEqual('my conventions', (self.repo / '.agents/skills/android-harness/references/custom.md').read_text())
        self.assertEqual('old', (self.repo / '.harness-setup/previous-engine/VERSION').read_text())

    def test_verification_failure_rolls_back(self):
        def fail(**kwargs):
            installer.place_engine(self.repo, self.kit, {})
            return {'success': False}
        with patch.object(installer, '_execute_install_or_update', side_effect=fail):
            with self.assertRaises(RuntimeError):
                installer.execute_install_or_update(repo=self.repo, kit=self.kit)
        self.assertEqual('old', (self.repo / '.agents/VERSION').read_text())

    def test_restart_recovers_interrupted_swap(self):
        installer.place_engine(self.repo, self.kit, {})
        def fail(**kwargs):
            self.assertEqual('old', (self.repo / '.agents/VERSION').read_text())
            raise OSError('network unavailable')
        with patch.object(installer, '_execute_install_or_update', side_effect=fail):
            with self.assertRaises(OSError):
                installer.execute_install_or_update(repo=self.repo, kit=self.kit)
        self.assertEqual('old', (self.repo / '.agents/VERSION').read_text())


if __name__ == '__main__':
    unittest.main()
