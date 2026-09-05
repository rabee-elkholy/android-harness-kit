"""Optional typed reviewer claims; artifact freshness does not prove semantics."""
import hashlib
import json
from pathlib import Path

from _evidence import matches


def checks_valid(report: dict, identity: dict, repo: Path) -> bool:
    if not isinstance(report, dict):
        return False
    checks = report.get('checks', [])
    if not isinstance(checks, list):
        return False
    seen = set()
    for check in checks:
        if not isinstance(check, dict):
            return False
        name = check.get('scenario')
        if not isinstance(name, str) or not name.strip() or name in seen:
            return False
        seen.add(name)
        status = check.get('status')
        if status == 'NOT_APPLICABLE':
            if not isinstance(check.get('reason'), str) or not check['reason'].strip():
                return False
            continue
        if status != 'VERIFIED':
            return False
        artifact = check.get('artifact')
        if not isinstance(artifact, dict) or not isinstance(artifact.get('path'), str):
            return False
        relative = Path(artifact['path'])
        if relative.is_absolute() or '..' in relative.parts:
            return False
        path = repo / relative
        try:
            if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
                return False
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != artifact.get('sha256'):
                return False
            evidence = json.loads(raw)
            if not isinstance(evidence, dict) or not matches(evidence, identity) or evidence.get('status') != 'PASS' or evidence.get('exit_code') != 0:
                return False
        except (OSError, ValueError, RuntimeError):
            return False
    return True
