"""Bind device observations to the exact validated build and installation."""
from pathlib import Path

from _evidence import context, matches
from _gate_results import read_gate_result, gate_artifact_name
from _snapshot import file_digest


def current_build(apk: Path, task: str) -> dict:
    from _repo_files import REPO
    build = read_gate_result(gate_artifact_name(task)) or {}
    if not matches(build, context()) or build.get('status') != 'PASS' or build.get('exit_code') != 0:
        raise ValueError('No current successful build evidence; assemble this snapshot first')
    rel = apk.resolve().relative_to(REPO.resolve()).as_posix()
    digest = file_digest(apk, REPO)
    if build.get('apks', {}).get(rel) != digest:
        raise ValueError('APK does not match the recorded build output')
    return {'apk_sha256': digest, 'build_run_id': build['run_id'], 'apk_path': rel}


def validate_delivery(bits: dict) -> str:
    from _repo_files import REPO
    install = read_gate_result('device_install') or {}
    try:
        binding = current_build(REPO / install.get('apk_path', ''), bits['assemble_task'])
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        return str(exc)
    for field, expected in binding.items():
        if install.get(field) != expected:
            return 'Installation refers to a different APK/build'
    keys = ['device_launch', 'device_smoke']
    if bits.get('device_mode') == 'manual_only':
        keys.append('manual_signoff')
    for key in keys:
        rec = read_gate_result(key) or {}
        if any(rec.get(k) != install.get(k) for k in ('apk_sha256', 'build_run_id', 'serial', 'application_id')):
            return key + ' does not match the installation'
        if rec.get('install_run_id') != install.get('run_id'):
            return key + ' predates the current installation'
    smoke = read_gate_result('device_smoke') or {}
    if not smoke.get('steps'):
        return 'No completed smoke steps recorded'
    if bits.get('device_mode') not in ('manual_only', 'autonomous_e2e'):
        return 'Unknown device verification mode'
    return ''
