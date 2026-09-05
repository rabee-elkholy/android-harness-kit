"""Exercise the runner/report/baseline pipeline with a real subprocess fixture."""
import contextlib
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from _delivery_integrity_selftest import DeliveryTest
import baseline_capture
import run_tests_gate
import run_gradle_task
from _test_reports import report_dir

FIXTURE = '''import os, sys
from pathlib import Path
case = os.environ.get('FIXTURE_CASE', 'old')
report = Path('app/build/test-results/testDebugUnitTest/TEST-Fixture.xml')
if case == 'compile':
 print('> Task :app:compileDebugKotlin FAILED')
 print('e: file.kt:1:1: compilation failed')
 sys.exit(1)
if case == 'missing':
 print('> Task :app:testDebugUnitTest NO-SOURCE')
 print('BUILD SUCCESSFUL')
 sys.exit(0)
report.parent.mkdir(parents=True, exist_ok=True)
if case == 'corrupt':
 report.write_text('<broken')
 print('BUILD SUCCESSFUL')
 sys.exit(0)
failures = '' if case == 'pass' else '<failure type="AssertionError" message="'+case+'"/>'
report.write_text('<testsuite><testcase classname="Fixture" name="test">'+failures+'</testcase></testsuite>')
if failures:
 print('> Task :app:testDebugUnitTest FAILED')
 print('There were failing tests. See the report')
 print('BUILD FAILED')
 sys.exit(1)
print('> Task :app:testDebugUnitTest')
print('BUILD SUCCESSFUL')
'''


class BaselinePipelineTest(DeliveryTest):
    # Reuse fixture helpers without inheriting the delivery tests.
    def setUp(self):
        super().setUp()
        for mod in (baseline_capture, run_tests_gate):
            self.stack.enter_context(patch.object(mod, 'REPO', self.repo))
        self.stack.enter_context(patch.object(run_gradle_task, 'REPO_ROOT', self.repo))
        (self.repo / 'fixture.py').write_text(FIXTURE)
        if os.name == 'nt':
            (self.repo / 'gradlew.bat').write_text('@"' + sys.executable + '" fixture.py %*\n')
        else:
            import shlex
            (self.repo / 'gradlew').write_text('#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' fixture.py "$@"\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'runner fixture')

    def capture_baseline(self):
        with patch.dict(os.environ, {'FIXTURE_CASE': 'old'}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, baseline_capture.main(['--run-tests']))
        self.assertEqual(1, len(baseline_capture.load_baseline()['unit_tests']))

    def run_case(self, case):
        with patch.dict(os.environ, {'FIXTURE_CASE': case}), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return run_tests_gate.main([])

    def test_known_assertion_failure_is_ignored(self):
        self.capture_baseline()
        self.assertEqual(0, self.run_case('old'))

    def test_changed_failure_is_regression(self):
        self.capture_baseline()
        self.assertEqual(1, self.run_case('new'))

    def test_compiler_failure_never_uses_baseline(self):
        self.capture_baseline()
        self.assertNotEqual(0, self.run_case('compile'))

    def test_missing_reports_cannot_reuse_old_reports(self):
        self.capture_baseline()
        self.assertEqual(1, self.run_case('missing'))

    def test_corrupt_reports_block(self):
        self.assertEqual(1, self.run_case('corrupt'))

    def test_valid_passing_reports(self):
        self.assertEqual(0, self.run_case('pass'))

    def test_dirty_build_configuration_prevents_baseline(self):
        (self.repo / 'build.gradle').write_text('changed')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, baseline_capture.main([]))


# Inherit only fixture methods: unittest discovers inherited test_* otherwise.
for name in dir(DeliveryTest):
    if name.startswith('test_') and name not in BaselinePipelineTest.__dict__:
        setattr(BaselinePipelineTest, name, None)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BaselinePipelineTest)
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
