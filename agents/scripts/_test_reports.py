"""Strict reports for one explicit Gradle test task; no historical report globbing."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET


def report_dir(repo: Path, task: str) -> Path:
    if not re.fullmatch(r'(?::[A-Za-z0-9_.-]+)+', task):
        raise ValueError('Use a fully qualified Gradle test task')
    parts = task.strip(':').split(':')
    if any(part in ('.', '..') for part in parts):
        raise ValueError('Invalid Gradle task path')
    return repo.joinpath(*parts[:-1], 'build', 'test-results', parts[-1])


def prepare_reports(repo: Path, task: str) -> None:
    directory = report_dir(repo, task)
    if directory.is_symlink() or not directory.resolve().is_relative_to(repo.resolve()):
        raise ValueError('Report directory escapes checkout')
    for path in directory.glob('TEST-*.xml'):
        path.unlink()


def read_reports(repo: Path, task: str) -> dict:
    paths = sorted(report_dir(repo, task).glob('TEST-*.xml'))
    if not paths:
        raise ValueError('No current test reports for ' + task)
    total, skipped, failures = 0, 0, []
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
            raise ValueError('Unsafe test report path')
        root = ET.parse(path).getroot()
        if root.tag not in ('testsuite', 'testsuites'):
            raise ValueError('Unknown JUnit report root')
        for case in root.iter('testcase'):
            total += 1
            if case.find('skipped') is not None:
                skipped += 1
            failure = case.find('failure')
            if failure is None:
                failure = case.find('error')
            if failure is not None:
                name = f"{case.get('classname', '')}#{case.get('name', '')}"
                signature = [task, name, failure.tag, failure.get('type', ''), failure.get('message', '')]
                fingerprint = hashlib.sha256(json.dumps(signature, ensure_ascii=True).encode()).hexdigest()
                failures.append({'fingerprint': fingerprint, 'test_name': name, 'task': task,
                                 'message': failure.get('message', '')[:300]})
    if total == 0 or skipped == total:
        raise ValueError('No executed tests; NO-SOURCE/all-skipped is not a test PASS')
    return {'total': total, 'skipped': skipped, 'failures': failures,
            'reports': [p.relative_to(repo).as_posix() for p in paths]}


def execute_tests(repo: Path, task: str) -> tuple[int, dict, dict]:
    import run_gradle_task
    with run_gradle_task.execution_lock():
        prepare_reports(repo, task)
        code = run_gradle_task._run_gradle([task, '--rerun-tasks', '--no-build-cache'])
        result = run_gradle_task.LAST_RESULT
        if code and (code == 30 or not result.get('test_assertion_failure')):
            return code, result, {}
        if result.get('status') == 'STALE':
            return 1, result, {}
        reports = read_reports(repo, task)
        if code and not reports['failures']:
            raise ValueError('Gradle failed but reports do not explain the failure')
        return code, result, reports
