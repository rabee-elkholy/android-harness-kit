"""Git-backed adversarial tests for additive routing, batches and scenario claims."""
import contextlib
import hashlib
import io
import json
import unittest
from unittest.mock import patch

import _delivery_integrity_selftest as delivery
import _hook_state
import _evidence
import _snapshot
import pre_tool_safety as safety
import record_review
from _android_review_scope import review_scope
from _review_batches import register_batch
from _review_contract import required_keys, LEAF_ALIASES, LEAF_PASS_VALUES
from _report_evidence import checks_valid


class ResilienceTest(delivery.DeliveryTest):
    def pending(self):
        self.src.write_text('@Composable fun Screen() {}\n')
        pkg, record = self.approved_fixture()
        record.update(leaves={}, verdict='PENDING')
        _hook_state.write_verdict_record(pkg, record)
        return pkg, record

    def report(self, record, checks=None):
        out = {'summary': 'Fixture review', 'reviewed_files': ['Feature.kt'],
               'package_hash': record['package']['sha256'], 'snapshot_id': record['snapshot_id'], 'findings': []}
        if checks is not None:
            out['checks'] = checks
        return out

    def invoke(self, record, keys, conversation='batches'):
        args = {'Subagents': [{'TypeName': next(a for a in LEAF_ALIASES[k] if a.endswith('-agent')),
                               'Workspace': 'inherit', 'Prompt': 'HARNESS_REVIEW_PACKAGE=' + record['package']['path']}
                              for k in keys]}
        out = io.StringIO()
        with patch.object(safety, 'REPO', self.repo), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            safety.handle_invoke_subagent({'conversationId': conversation}, args)
        return json.loads(out.getvalue().splitlines()[-1])

    def policy(self, value):
        path = self.repo / '.agents/review-policy.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def test_indirect_ui_policy_adds_without_removing_required_roles(self):
        self.policy({'version': 1, 'paths': {'Feature.kt': ['ui_expert']}})
        keys = required_keys({})
        self.assertIn('ui_expert', keys)
        self.assertIn('test_quality', keys)
        self.assertEqual(7, len(keys))

    def test_inactive_policy_rule_does_not_activate_ui(self):
        self.policy({'version': 1, 'paths': {'other': ['ui_expert']}})
        self.assertNotIn('ui_expert', required_keys({}))

    def test_invalid_or_subtractive_policy_is_rejected(self):
        for value in ({'version': 1, 'exclude': ['test_quality']},
                      {'version': 1, 'require': ['unknown']},
                      {'version': 1, 'paths': {'../external': ['ui_expert']}},
                      {'version': 1, 'paths': {'inactive': 'ui_expert'}}):
            with self.subTest(value=value):
                self.policy(value)
                with self.assertRaises(ValueError):
                    required_keys({})

    def test_policy_edit_stales_existing_evidence(self):
        self.policy({'version': 1, 'require': []})
        self.approved_fixture()
        self.policy({'version': 1, 'require': ['ui_expert']})
        self.assertEqual('STALE', self.verdict()['status'])

    def test_comment_candidate_never_downgrades_review(self):
        self.src.write_text('fun value() = 1\n// explanation\n')
        scope = review_scope(self.repo, ['Feature.kt'])
        self.assertIn('Feature.kt', scope['cosmetic_candidates_advisory_only'])
        self.assertIn('test_quality', scope['required_reviewers'])

    def test_native_two_batches_preserve_reports_and_count_one_round(self):
        pkg, record = self.pending()
        keys = required_keys(record)
        self.assertEqual('allow', self.invoke(record, keys[:5])['decision'])
        for key in keys[:5]:
            self.assertTrue(record_review.record_leaf_verdict(pkg, key, LEAF_PASS_VALUES[key], report=self.report(record)))
        self.assertFalse(safety.check_subagents_barrier('batches')[0])
        self.assertEqual('allow', self.invoke(record, keys[5:])['decision'])
        self.assertEqual(1, _hook_state.invoke_count('batches', 'review'))
        self.assertEqual(5, len(_hook_state.read_verdict_record(pkg)['leaves']))
        for key in keys[5:]:
            self.assertTrue(record_review.record_leaf_verdict(pkg, key, LEAF_PASS_VALUES[key], report=self.report(record)))
        self.assertTrue(safety.check_subagents_barrier('batches')[0])
        self.assertEqual('APPROVED', self.verdict()['status'])

    def test_duplicate_batch_and_cross_conversation_rejected_without_mutation(self):
        pkg, record = self.pending()
        register_batch(pkg, ['bug_reviewer'], 'one')
        before = _hook_state.read_verdict_record(pkg)
        for keys, conv in ((['bug_reviewer'], 'one'), (['ui_expert'], 'two')):
            with self.assertRaises(ValueError):
                register_batch(pkg, keys, conv)
            self.assertEqual(before, _hook_state.read_verdict_record(pkg))

    def test_stale_second_batch_rejected(self):
        pkg, record = self.pending()
        self.assertEqual('allow', self.invoke(record, ['bug_reviewer'])['decision'])
        self.src.write_text('fun changed() = 2\n')
        self.assertEqual('deny', self.invoke(record, ['test_quality'])['decision'])
        self.assertFalse(safety.check_subagents_barrier('batches')[0])

    def test_mixed_package_batch_rejected(self):
        pkg, record = self.pending()
        self.assertEqual('allow', self.invoke(record, ['bug_reviewer'])['decision'])
        other_path = _hook_state.state_path().parent / 'packages/other.diff'
        other_path.write_text('different review package')
        digest = _snapshot.file_digest(other_path, self.repo)
        other = dict(record, package={'path': str(other_path), 'sha256': digest})
        _hook_state.write_verdict_record(digest[:12], other)
        self.assertEqual('deny', self.invoke(other, ['ui_expert'])['decision'])
        self.assertEqual(1, _hook_state.invoke_count('batches', 'review'))

    def test_ui_source_batch_requires_actual_ui_report(self):
        pkg, record = self.pending()
        keys = required_keys(record)
        self.assertEqual('allow', self.invoke(record, keys[:5])['decision'])
        for key in keys[:-1]:
            self.assertTrue(record_review.record_leaf_verdict(pkg, key, LEAF_PASS_VALUES[key], report=self.report(record)))
        self.assertFalse(safety.check_subagents_barrier('batches')[0])
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_successful_artifact_reference_then_tampering_blocks_delivery(self):
        pkg, record = self.approved_fixture()
        evidence = _evidence.context() | {'status': 'PASS', 'exit_code': 0}
        path = _hook_state.state_path().parent / 'scenario.json'
        _evidence.atomic_json(path, evidence)
        check = {'scenario': 'state restoration', 'status': 'VERIFIED',
                 'artifact': {'path': path.relative_to(self.repo).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
        self.assertTrue(record_review.record_leaf_verdict(pkg, 'bug_reviewer', 'BUG_PASS', report=self.report(record, [check])))
        self.assertEqual('APPROVED', self.verdict()['status'])
        _evidence.atomic_json(path, evidence | {'status': 'FAIL', 'exit_code': 1})
        self.assertNotEqual('APPROVED', self.verdict()['status'])

    def test_blocked_and_unbound_claims_cannot_pass(self):
        pkg, record = self.approved_fixture()
        for check in ({'scenario': 'ios', 'status': 'BLOCKED'},
                      {'scenario': 'ios', 'status': 'VERIFIED'},
                      {'scenario': 'ios', 'status': 'NOT_APPLICABLE', 'reason': ''},
                      {'scenario': 'ios', 'status': 'VERIFIED', 'artifact': {'path': '../escape', 'sha256': 'a' * 64}}):
            with self.subTest(check=check), contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(record_review.record_leaf_verdict(pkg, 'bug_reviewer', 'BUG_PASS', report=self.report(record, [check])))

    def test_failed_or_wrong_task_artifact_rejected_even_with_matching_hash(self):
        pkg, record = self.approved_fixture()
        path = _hook_state.state_path().parent / 'scenario.json'
        for extra in ({'status': 'FAIL'}, {'task_id': 'other'}, {'snapshot_id': 'old'}):
            _evidence.atomic_json(path, _evidence.context() | {'status': 'PASS', 'exit_code': 0} | extra)
            check = {'scenario': 'test', 'status': 'VERIFIED', 'artifact': {
                'path': path.relative_to(self.repo).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}
            self.assertFalse(checks_valid(self.report(record, [check]), record, self.repo))

    def test_not_applicable_requires_reason_and_no_duplicate_scenarios(self):
        pkg, record = self.approved_fixture()
        check = {'scenario': 'ios', 'status': 'NOT_APPLICABLE', 'reason': 'No iOS target in this project'}
        self.assertTrue(checks_valid(self.report(record, [check]), record, self.repo))
        self.assertFalse(checks_valid(self.report(record, [check, check]), record, self.repo))


if __name__ == '__main__':
    unittest.main()
