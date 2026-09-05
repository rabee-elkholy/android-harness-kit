"""Install each distribution outside the source tree and exercise its CLI/assets."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import venv


def main():
    artifacts = sorted(Path('dist').glob('*.whl')) + sorted(Path('dist').glob('*.tar.gz'))
    if len(artifacts) != 2:
        raise SystemExit('Expected exactly one wheel and one sdist')
    for artifact in artifacts:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            venv.EnvBuilder(with_pip=True).create(root / 'venv')
            python = root / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            subprocess.run([str(python), '-m', 'pip', 'install', str(artifact.resolve())], cwd=root, check=True)
            code = '''from pathlib import Path
import harness_cli
kit = Path(harness_cli.__file__).parent
assert harness_cli._has_engine(kit), 'Installed wheel has no engine'
for name in ['VERSION', 'EVIDENCE.md', 'tool-adapters/README.md', 'hooks.json', 'rules/harness-rules.md', 'subagents/bug-reviewer-agent.json', 'scripts/final_verdict.py', 'scripts/_android_review_scope.py', 'scripts/_review_batches.py', 'scripts/_review_policy.py', 'scripts/_report_evidence.py', 'workflows/review-delivery.md', 'skills/android-state-recovery/SKILL.md', 'skills/android-release-verification/SKILL.md', 'skills/kmp-boundary-verification/SKILL.md', 'skills/android-harness/references/android-competency-matrix.md']:
 assert (kit / 'agents' / name).is_file(), name
import sys, json, subprocess
sys.path.insert(0, str(kit / 'agents/scripts'))
from install_or_update import execute_install_or_update
repo = Path.cwd() / 'client'
repo.mkdir()
(repo / 'gradlew').write_text('#!/bin/sh\\nexit 0\\n')
(repo / 'settings.gradle').write_text("include ':app'\\n")
subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
answers = Path.cwd() / 'answers.json'
answers.write_text(json.dumps({'product': 'Fixture', 'application_id': 'com.example.fixture', 'tools': ['codex'], 'pm_provider': 'none', 'git_gate': 'no', 'backup': False, 'device_verification': 'disabled'}))
result = execute_install_or_update(repo=repo, kit=kit, answers_path=str(answers), skip_doctor=True)
assert result['success']
assert (repo / '.agents/EVIDENCE.md').is_file()
assert (repo / '.agents/scripts/_product.py').is_file()
assert (repo / '.agents/scripts/_android_review_scope.py').is_file()
assert (repo / '.agents/skills/android-harness/references/android-competency-matrix.md').is_file()
assert (repo / 'AGENTS.md').is_file()
print(kit)
'''
            subprocess.run([str(python), '-c', code], cwd=root, check=True)
            subprocess.run([str(python), '-m', 'harness_cli', 'version'], cwd=root, check=True)
            print('Distribution smoke passed: ' + artifact.name)


if __name__ == '__main__':
    main()
