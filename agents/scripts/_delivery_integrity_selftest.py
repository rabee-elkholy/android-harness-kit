"""Real Git fixtures exercise the delivery contract, without a device or network."""
from __future__ import annotations

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _repo_files
import _hook_state
import _evidence
import _gate_results as gates
import _snapshot
import final_verdict
import record_review
import record_device_verification
from _review_contract import LEAF_KEYS, LEAF_PASS_VALUES


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.src = self.repo / 'Feature.kt'
        self.src.write_text('fun value() = 1\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        self.src.write_text('fun value() = 2\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith('HARNESS_')}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, env, clear=True))
        for module in (_repo_files, final_verdict):
            self.stack.enter_context(patch.object(module, 'REPO', self.repo))
        self.bits = {'unit_test_task': ':app:testDebugUnitTest', 'assemble_task': ':app:assembleDebug', 'device_mode': 'disabled'}

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, stderr=subprocess.STDOUT).decode().strip()

    def result(self, name, **extra):
        run = gates.GateRun(name)
        return run.finish({'status': 'PASS', 'exit_code': 0, **extra})

    def reviews(self, tests=False):
        ctx = _evidence.context()
        package = _hook_state.state_path().parent / 'packages' / 'fixture.diff'
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text('reviewed changes\n')
        digest = _snapshot.file_digest(package, self.repo)
        record = ctx | {'package': {'path': str(package), 'sha256': digest},
                        'tree_fingerprint': ctx['snapshot_id'], 'files': {'Feature.kt': _snapshot.file_digest(self.src, self.repo)},
                        'contains_tests': tests, 'leaves': {}, 'findings': [], 'verdict': 'APPROVED'}
        from _review_contract import required_keys
        for key in required_keys(record):
            record['leaves'][key] = {'token': LEAF_PASS_VALUES[key], 'report': {'summary': 'Fixture reviewer report'}}
        _hook_state.write_verdict_record(digest[:12], record)
        _evidence.atomic_json(_hook_state.state_path().with_name('review_ledger.json'),
                              ctx | {'sha256': digest, 'tree_fingerprint': ctx['snapshot_id']})
        return digest[:12], record

    def approved_fixture(self):
        self.result('unit_tests', task=self.bits['unit_test_task'])
        self.result('preflight')
        self.result(gates.gate_artifact_name(self.bits['assemble_task']), task=self.bits['assemble_task'])
        return self.reviews()

    def verdict(self):
        return final_verdict.build_verdict(bits=self.bits)

    def test_all_current_evidence_approves(self):
        self.approved_fixture()
        verdict = self.verdict()
        self.assertEqual('APPROVED', verdict['status'], verdict)
        self.assertTrue(all(c['status'] == 'PASS' for c in verdict['checks']))

    def test_production_change_cannot_approve_without_test_review(self):
        pkg, record = self.approved_fixture()
        record['leaves'].pop('test_quality')
        _hook_state.write_verdict_record(pkg, record)
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_ui_change_cannot_approve_without_ui_review(self):
        self.src.write_text('@Composable fun Screen() {}\n')
        pkg, record = self.approved_fixture()
        record['leaves'].pop('ui_expert')
        _hook_state.write_verdict_record(pkg, record)
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_ui_report_recording_completes_dynamic_roster(self):
        self.src.write_text('@Composable fun Screen() {}\n')
        pkg, record = self.approved_fixture()
        record['leaves'].pop('ui_expert')
        record['verdict'] = 'PENDING'
        _hook_state.write_verdict_record(pkg, record)
        report = {'summary': 'Reviewed state and UI contract',
                  'package_hash': record['package']['sha256'],
                  'snapshot_id': record['snapshot_id'], 'reviewed_files': ['Feature.kt'], 'findings': []}
        self.assertTrue(record_review.record_leaf_verdict(pkg, 'ui_expert', 'UI_PASS', report=report))
        self.assertEqual('APPROVED', self.verdict()['status'])

    def test_native_hook_uses_same_roster_and_requires_ui_token(self):
        import pre_tool_safety as safety
        self.src.write_text('@Composable fun Screen() {}\n')
        pkg, record = self.approved_fixture()
        # An edited advisory count must not downgrade the actual requirements.
        record['required_leaves_count'] = 5
        _hook_state.write_verdict_record(pkg, record)
        keys = safety._required_review_keys(pkg)
        self.assertEqual(7, len(keys))
        tokens = tuple(LEAF_PASS_VALUES[key] for key in keys)
        self.assertFalse(safety._tail_has_verdicts(' '.join(tokens[:-1]), required_tokens=tokens))
        self.assertTrue(safety._tail_has_verdicts(' '.join(tokens), required_tokens=tokens))

    def test_missing_gates_block(self):
        self.reviews()
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_same_file_edit_invalidates_all_evidence(self):
        self.approved_fixture()
        self.src.write_text('fun value() = 3\n')
        self.assertEqual('STALE', self.verdict()['status'])

    def test_new_review_does_not_refresh_old_tests(self):
        self.approved_fixture()
        self.src.write_text('fun value() = 3\n')
        self.reviews()
        self.assertNotEqual('APPROVED', self.verdict()['status'])
        self.assertEqual('STALE', self.verdict()['checks'][0]['status'])

    def test_legacy_result_rejected(self):
        self.approved_fixture()
        gates.write_gate_result('unit_tests', {'status': 'PASS', 'exit_code': 0, 'git_sha': self.git('rev-parse', 'HEAD')})
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_contradictory_result_rejected(self):
        self.approved_fixture()
        self.result('unit_tests', exit_code=1)
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_unknown_result_rejected(self):
        self.approved_fixture()
        self.result('unit_tests', status='WAIVED')
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_environment_error_is_environment_blocked(self):
        self.approved_fixture()
        self.result('unit_tests', status='ENV', exit_code=30)
        self.assertEqual('ENV_BLOCKED', self.verdict()['status'])

    def test_changed_during_run_invalidates(self):
        run = gates.GateRun('preflight')
        self.src.write_text('fun value() = 42\n')
        result = run.finish({'status': 'PASS', 'exit_code': 0})
        self.assertEqual('STALE', result['status'])
        self.assertEqual(1, result['exit_code'])

    def test_old_run_cannot_overwrite_new_run(self):
        old = gates.GateRun('preflight')
        new = gates.GateRun('preflight')
        new.finish({'status': 'FAIL', 'exit_code': 1})
        self.assertEqual('STALE', old.finish({'status': 'PASS', 'exit_code': 0})['status'])
        self.assertEqual('FAIL', gates.read_gate_result('preflight')['status'])

    def test_tasks_do_not_share_results(self):
        self.result('preflight')
        with patch.dict(os.environ, {'HARNESS_TASK_ID': 'other-task'}):
            self.assertIsNone(gates.read_gate_result('preflight'))

    def test_corrupt_json_is_not_pass(self):
        self.approved_fixture()
        (gates.results_dir() / 'unit_tests.json').write_text('{')
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_changed_package_is_rejected(self):
        _, rec = self.approved_fixture()
        Path(rec['package']['path']).write_text('tampered')
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_partial_package_rejected(self):
        digest, rec = self.approved_fixture()
        rec['partial'] = True
        _hook_state.write_verdict_record(digest, rec)
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_unresolved_finding_blocks(self):
        digest, rec = self.approved_fixture()
        rec['findings'] = ['unresolved bug']
        _hook_state.write_verdict_record(digest, rec)
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_test_change_requires_sixth_leaf(self):
        (self.repo / 'FeatureTest.kt').write_text('class FeatureTest\n')
        pkg, record = self.approved_fixture()
        record['leaves'].pop('test_quality')
        _hook_state.write_verdict_record(pkg, record)
        self.assertNotEqual('APPROVED', self.verdict()['status'])
        self.reviews(tests=True)
        self.assertEqual('APPROVED', self.verdict()['status'])

    def test_bulk_approval_never_creates_a_verdict(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(record_review.approve_all_leaves('a' * 12))
        self.assertIsNone(_hook_state.read_verdict_record('a' * 12))

    def test_structured_review_can_be_revoked(self):
        digest, rec = self.reviews()
        report = {'summary': 'Checked value contract', 'package_hash': rec['package']['sha256'],
                  'snapshot_id': rec['snapshot_id'], 'reviewed_files': ['Feature.kt'], 'findings': ['bug']}
        self.assertTrue(record_review.record_leaf_verdict(digest, 'bug_reviewer', 'FAIL', report=report))
        self.assertNotEqual('APPROVED', _hook_state.read_verdict_record(digest)['verdict'])

    def test_explicit_findings_are_not_discarded(self):
        digest, rec = self.reviews()
        report = {"summary": "review", "package_hash": rec["package"]["sha256"],
                  "snapshot_id": rec["snapshot_id"], "reviewed_files": ["Feature.kt"], "findings": []}
        self.assertTrue(record_review.record_leaf_verdict(digest, "bug_reviewer", "BUG_PASS", findings=["MAJOR defect"], report=report))
        self.assertNotEqual("APPROVED", _hook_state.read_verdict_record(digest)["verdict"])

    def test_local_policy_change_invalidates(self):
        policy = self.repo / '.agents' / 'rules' / 'policy.md'
        policy.parent.mkdir(parents=True)
        policy.write_text('first')
        before = _evidence.context()
        policy.write_text('second')
        self.assertFalse(_evidence.matches(before, _evidence.context()))

    def test_unicode_paths_and_rename_and_delete(self):
        target = self.repo / ('اختبار space.kt' if os.name == 'nt' else 'اختبار -> space.kt')
        self.src.rename(target)
        paths = _repo_files.changed_paths()
        self.assertIn(self.src, paths)
        self.assertIn(target, paths)
        before = _snapshot.capture(self.repo)['snapshot_id']
        target.unlink()
        self.assertNotEqual(before, _snapshot.capture(self.repo)['snapshot_id'])

    @unittest.skipIf(os.name == 'nt', 'POSIX newline filename / symlink fixture')
    def test_newline_and_symlink_escape(self):
        p = self.repo / 'line\nbreak.kt'
        p.write_text('x')
        self.assertIn(p, _repo_files.changed_paths())
        p.unlink()
        p.symlink_to(self.repo.parent / 'outside')
        with self.assertRaises(RuntimeError):
            _snapshot.capture(self.repo)

    def test_uninstall_is_not_device_verification(self):
        self.approved_fixture()
        self.bits['device_mode'] = 'manual_only'
        self.result('device', action='uninstall')
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_current_device_reports_and_manual_signoff(self):
        self.approved_fixture()
        self.bits['device_mode'] = 'manual_only'
        apk = self.repo / 'app/build/outputs/apk/debug/app-debug.apk'
        apk.parent.mkdir(parents=True)
        apk.write_bytes(b'fixture APK, not executable')
        rel, digest = apk.relative_to(self.repo).as_posix(), _snapshot.file_digest(apk, self.repo)
        build = self.result(gates.gate_artifact_name(self.bits['assemble_task']), task=self.bits['assemble_task'], apks={rel: digest})
        binding = {'apk_path': rel, 'apk_sha256': digest, 'build_run_id': build['run_id'], 'serial': 'fixture-device', 'application_id': 'fixture.app'}
        install = self.result('device_install', **binding)
        self.result('device_launch', **binding, install_run_id=install['run_id'])
        report = {'serial': binding['serial'], 'apk_sha256': digest, 'result': 'PASS',
                  'steps': [{'action': 'open', 'expected': 'screen', 'observed': 'screen', 'passed': True}]}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, record_device_verification.record('smoke', report))
            self.assertEqual(0, record_device_verification.record('manual', report))
        self.assertEqual('APPROVED', self.verdict()['status'])
        apk.write_bytes(b'wrong APK')
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_cli_and_aggregator_agree(self):
        import shutil
        source = Path(__file__).resolve().parent
        installed = self.repo / ".agents" / "scripts"
        shutil.copytree(source, installed, ignore=shutil.ignore_patterns("__pycache__"))
        (installed.parent / "VERSION").write_text("fixture")
        (installed / "_product.py").write_text('UNIT_TEST_TASK=":app:testDebugUnitTest"\nASSEMBLE_TASK=":app:assembleDebug"\nDEVICE_VERIFICATION_MODE="disabled"\n')
        self.stack.enter_context(patch.object(_evidence, "ENGINE_ROOT", installed))
        (self.repo / "gradlew").write_text("#!/bin/sh\nexit 0\n")
        self.approved_fixture()
        cli = source.parents[1] / "harness_cli.py"
        if not cli.is_file():
            self.skipTest("CLI file only ships at the distribution root")
        env = os.environ.copy()
        env["HARNESS_REPO"] = str(self.repo)
        proc = subprocess.run([sys.executable, str(cli), "verify", "--kit", str(source.parents[1]), "--repo", str(self.repo)],
                              capture_output=True, text=True, env=env)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn('"status": "APPROVED"', proc.stdout)
        self.src.write_text("changed after review")
        proc = subprocess.run([sys.executable, str(cli), "verify", "--kit", str(source.parents[1]), "--repo", str(self.repo)],
                              capture_output=True, text=True, env=env)
        self.assertEqual(1, proc.returncode)

    def test_exit_code_contract(self):
        self.assertEqual(0, final_verdict.exit_code_for('APPROVED'))
        self.assertEqual(30, final_verdict.exit_code_for('ENV_BLOCKED'))
        for status in ('STALE', 'BLOCKED', 'EXPIRED', 'UNKNOWN'):
            self.assertEqual(1, final_verdict.exit_code_for(status))


if __name__ == '__main__':
    unittest.main()
