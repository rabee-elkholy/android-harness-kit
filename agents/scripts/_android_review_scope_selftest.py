"""Routing regressions with actual Git history, including deleted UI sources."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from _android_review_scope import review_scope
from _review_contract import is_test_file


class ScopeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        self.git('commit', '--allow-empty', '-qm', 'initial')

    def git(self, *args):
        subprocess.run(['git', *args], cwd=self.repo, check=True, capture_output=True)

    def scope(self, path, content=''):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return review_scope(self.repo, [path])['required_reviewers']

    def test_production_without_test_changes_requires_test_reviewer(self):
        keys = self.scope('shared/src/commonMain/kotlin/Logic.kt', 'fun compute() = 1')
        self.assertIn('test_quality', keys)
        self.assertNotIn('ui_expert', keys)

    def test_compose_addition_requires_both_specialists(self):
        keys = self.scope('feature/Widget.kt', '@Composable fun Widget() {}')
        self.assertEqual(7, len(keys))
        self.assertIn('ui_expert', keys)

    def test_removed_annotation_and_deleted_file_still_require_ui(self):
        self.scope('Widget.kt', '@Composable fun Widget() {}')
        self.git('add', '.')
        self.git('commit', '-qm', 'ui')
        self.assertIn('ui_expert', self.scope('Widget.kt', 'fun Widget() {}'))
        (self.repo / 'Widget.kt').unlink()
        self.assertIn('ui_expert', review_scope(self.repo, ['Widget.kt'])['required_reviewers'])

    def test_qualified_resources(self):
        for folder in ('layout-land', 'values-ar', 'values-night', 'navigation', 'drawable-v24'):
            with self.subTest(folder=folder):
                self.assertIn('ui_expert', self.scope('app/src/main/res/' + folder + '/a.xml', '<resources/>'))

    def test_build_manifest_and_release_changes_require_test_review(self):
        for path in ('build.gradle.kts', 'AndroidManifest.xml', 'gradle/libs.versions.toml', 'consumer-rules.pro'):
            with self.subTest(path=path):
                self.assertIn('test_quality', self.scope(path))

    def test_docs_and_kit_python_do_not_activate_android_specialists(self):
        for path in ('README.md', 'agents/scripts/tool.py'):
            self.assertEqual(5, len(self.scope(path)))

    def test_kmp_and_custom_test_sources(self):
        for path in ('shared/src/commonTest/Foo.kt', 'shared/src/iosTest/Foo.kt', 'src/testFixtures/FooTest.kt'):
            self.assertTrue(is_test_file(path))
            self.assertIn('test_quality', self.scope(path))

    def test_ui_test_does_not_trigger_ui_source_heuristic(self):
        keys = self.scope('src/androidTest/ScreenTest.kt', 'import androidx.compose.ui.test.*')
        self.assertIn('test_quality', keys)
        self.assertNotIn('ui_expert', keys)

    def test_external_symlink_is_not_read(self):
        with tempfile.TemporaryDirectory() as other:
            external = Path(other) / 'secret.kt'
            external.write_text('@Composable fun Secret() {}')
            try:
                (self.repo / 'Alias.kt').symlink_to(external)
            except OSError:
                self.skipTest('symlink creation unavailable')
            self.assertNotIn('ui_expert', review_scope(self.repo, ['Alias.kt'])['required_reviewers'])


if __name__ == '__main__':
    unittest.main()
