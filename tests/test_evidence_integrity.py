"""Regression tests for delivery evidence; no Android SDK or remote services."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'agents' / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import _repo_files
import _hook_state
import final_verdict
import room_guard


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.file = self.repo / 'Feature.kt'
        self.file.write_text('fun value() = 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.patch = patch.object(_repo_files, 'REPO', self.repo)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.STDOUT).decode().strip()

    def test_same_path_new_content_invalidates_review(self):
        self.file.write_text('fun value() = 2\n')
        before = _hook_state.tree_code_fingerprint(self.repo)
        self.file.write_text('fun value() = error("broken")\n')
        self.assertNotEqual(before, _hook_state.tree_code_fingerprint(self.repo))

    def test_deletion_invalidates_review(self):
        before = _hook_state.tree_code_fingerprint(self.repo)
        self.file.unlink()
        self.assertIn(self.file, _repo_files.changed_paths())
        self.assertNotEqual(before, _hook_state.tree_code_fingerprint(self.repo))

    def test_build_configuration_is_protected(self):
        p = self.repo / 'build.gradle'
        p.write_text('// build one')
        before = _hook_state.tree_code_fingerprint(self.repo)
        p.write_text('// build two')
        self.assertNotEqual(before, _hook_state.tree_code_fingerprint(self.repo))

    def test_old_gate_cannot_pass_same_head(self):
        rec = {'status': 'PASS', 'exit_code': 0, 'git_sha': self.git('rev-parse', 'HEAD'),
               'tree_fingerprint': 'old'}
        check = final_verdict._normalize_check('unit_tests', rec, rec['git_sha'])
        self.assertNotEqual('PASS', check['status'])

    def test_room_comment_only_does_not_require_migration(self):
        db = self.repo / 'AppDatabase.kt'
        db.write_text('@Database(entities = [User::class], version = 1)\nabstract class AppDatabase : RoomDatabase()')
        entity = self.repo / 'User.kt'
        old = '@Entity data class User(val id: Int)\n'
        entity.write_text(old)
        self.git('add', '.')
        self.git('commit', '-qm', 'room fixture')
        entity.write_text(old + '// comment only\n')
        with patch.object(room_guard, 'REPO', self.repo):
            ok, message = room_guard.check_room_working_tree(['User.kt'])
        self.assertTrue(ok, message)


if __name__ == '__main__':
    unittest.main()
