"""Record explicit scenario evidence; install/start alone never satisfy delivery.

A report is a local attestation, not proof against a writer of this checkout.
Usage: record_device_verification.py --kind smoke|manual --report report.json
Report: {"serial": "...", "apk_sha256": "...", "result": "PASS"|"FAIL",
         "steps": [{"action": "...", "expected": "...", "observed": "...", "passed": true}]}
Manual reports additionally require interactive confirmation by the developer.
"""
import argparse
import json
from pathlib import Path
import sys

from _evidence import context, matches
from _gate_results import GateRun, read_gate_result


def record(kind: str, report: dict) -> int:
    gate = GateRun('device_smoke' if kind == 'smoke' else 'manual_signoff')
    installed = read_gate_result('device_install') or {}
    launch = read_gate_result('device_launch') or {}
    steps = report.get('steps')
    valid_steps = isinstance(steps, list) and bool(steps) and all(
        isinstance(s, dict) and all(isinstance(s.get(k), str) and s[k].strip() for k in ('action', 'expected', 'observed'))
        and isinstance(s.get('passed'), bool) for s in steps)
    valid = (matches(installed, context()) and matches(launch, context())
             and installed.get('status') == launch.get('status') == 'PASS'
             and launch.get('install_run_id') == installed.get('run_id')
             and report.get('serial') == installed.get('serial')
             and report.get('apk_sha256') == installed.get('apk_sha256') and valid_steps)
    passed = bool(valid and report.get('result') == 'PASS' and all(s['passed'] for s in steps))
    binding = {k: installed.get(k) for k in ('serial', 'apk_sha256', 'apk_path', 'build_run_id', 'application_id')}
    result = gate.finish(binding | {'install_run_id': installed.get('run_id'), 'steps': steps or [],
                                   'attestation': 'developer_terminal' if kind == 'manual' else 'self_reported',
                                   'status': 'PASS' if passed else 'FAIL', 'exit_code': 0 if passed else 1,
                                   'detail': 'Scenario report recorded' if valid else 'Invalid or stale scenario evidence'})
    print(result['detail'])
    return result['exit_code']


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['smoke', 'manual'], required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding='utf-8'))
    if args.kind == 'manual':
        if not sys.stdin.isatty():
            print('[REFUSED] Record manual sign-off in a developer terminal')
            return 1
        expected = report.get('result')
        if expected not in ('PASS', 'FAIL') or input('Confirm the observed report result (PASS/FAIL): ').strip() != expected:
            return 1
    return record(args.kind, report)


if __name__ == '__main__':
    sys.exit(main())
