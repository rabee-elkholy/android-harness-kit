"""Run-scoped gate results. Missing/legacy/stale artifacts never prove success."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from _evidence import atomic_json, context, locked, matches, new_run, task_key


def results_dir() -> Path:
    override = os.environ.get('HARNESS_RESULTS_DIR')
    if override:
        return Path(override)
    from _repo_files import REPO
    root = REPO / ('.agents' if (REPO / '.agents').is_dir() else 'agents') / 'state'
    return root / 'tasks' / task_key() / 'results'


def write_gate_result(name: str, data: dict, *, results_dir_override: Path | None = None) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
        raise ValueError('Invalid gate artifact name')
    directory = results_dir_override or results_dir()
    return atomic_json(directory / f'{name}.json', data)


def read_gate_result(name: str, *, results_dir_override: Path | None = None) -> dict | None:
    directory = results_dir_override or results_dir()
    try:
        data = json.loads((directory / f'{name}.json').read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


class GateRun:
    def __init__(self, name: str):
        self.name = name
        self.identity = new_run()
        self.directory = results_dir()
        with locked(self.directory / (name + '.lock')):
            write_gate_result(name, self.identity | {'status': 'RUNNING', 'exit_code': None},
                              results_dir_override=self.directory)

    def finish(self, data: dict) -> dict:
        record = data | self.identity | {'finished_at': time.time()}
        if not matches(self.identity, context()):
            record.update(status='STALE', exit_code=1, detail='Inputs changed during gate execution; rerun')
        with locked(self.directory / (self.name + '.lock')):
            latest = read_gate_result(self.name, results_dir_override=self.directory)
            if not latest or latest.get('run_id') != self.identity['run_id']:
                record.update(status='STALE', exit_code=1, detail='A newer gate run superseded this run')
                return record
            write_gate_result(self.name, record, results_dir_override=self.directory)
        return record


def sanitize_task(task: str) -> str:
    cleaned = re.sub(r'[^A-Za-z0-9]+', '-', str(task).strip().strip(':')).strip('-')
    return cleaned.lower()[:80] or 'gradle'


def gate_artifact_name(task: str) -> str:
    # Preserve familiar names while preventing truncation/case/punctuation collisions.
    import hashlib
    return f'gradle-{sanitize_task(task)}-{hashlib.sha256(task.encode()).hexdigest()[:10]}'


def current_head_sha() -> str:
    from _repo_files import REPO
    from _snapshot import git_bytes
    try:
        return git_bytes(REPO, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip()
    except (RuntimeError, OSError):
        return ''
