"""Run every declared selftest in an isolated process; report all failures."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'agents' / 'scripts'


def main():
    failed = []
    for script in sorted(SCRIPTS.glob('_*selftest.py')):
        env = os.environ.copy()
        for key in list(env):
            if key.startswith('HARNESS_') or key in ('CODEX_CLI', 'CODEX_SESSION_ID', 'CLAUDE_CODE', 'CLAUDE_CLI', 'CLAUDE_SESSION_ID', 'CURSOR_AGENT', 'CURSOR_WORKSPACE', 'VSCODE_GIT_ASKPASS_NODE'):
                env.pop(key, None)
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env, timeout=180)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = 124
        print(f'[{"PASS" if code == 0 else "FAIL"}] {script.name}: exit {code}', flush=True)
        if code:
            failed.append(script.name)
    proc = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py'], cwd=ROOT)
    if proc.returncode:
        failed.append('tests/')
    print('Failed suites: ' + (', '.join(failed) or 'none'))
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
