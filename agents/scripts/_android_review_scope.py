"""Conservative reviewer routing, not proof of Android semantic coverage.

Inspect both HEAD and working tree so deletions and removed annotations still
activate specialists. Unknown source layouts get test review rather than an
assumption that a source file cannot affect behavior.
"""
from pathlib import Path
import re
import subprocess

from _review_contract import LEAF_KEYS, is_test_file

UI_CODE = re.compile(r"@Composable\b|\b(?:setContentView|setContent|ViewBinding|DataBindingUtil)\b|androidx\.compose\.|android\.view\.")


def source_versions(repo: Path, relative: str) -> str:
    path = repo / relative
    parts = []
    # Never follow an external symlink just to classify a file.
    if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(repo.resolve()):
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    old = subprocess.run(["git", "show", "HEAD:" + relative], cwd=repo,
                         capture_output=True, encoding="utf-8", errors="replace")
    if old.returncode == 0:
        parts.append(old.stdout)
    return "\n".join(parts)


def review_scope(repo: Path, paths: list[str]) -> dict:
    reasons = {"test_quality": [], "ui_expert": []}
    cosmetic_candidates = []
    for raw in sorted(set(paths)):
        relative = raw.replace("\\", "/")
        lower = relative.lower()
        source = lower.endswith((".kt", ".java", ".kts", ".gradle"))
        if source:
            diff = subprocess.run(['git', 'diff', '--no-ext-diff', '--no-textconv', '-U0', 'HEAD', '--', relative],
                                  cwd=repo, capture_output=True, encoding='utf-8', errors='replace')
            lines = [line[1:].strip() for line in diff.stdout.splitlines()
                     if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
            if diff.returncode == 0 and lines and all(not line or line.startswith(('//', '/*', '*', '*/')) for line in lines):
                cosmetic_candidates.append(relative)
        resource = bool(re.search(r"(?:^|/)res/", lower))
        manifest = lower.endswith("androidmanifest.xml")
        release = lower.endswith((".pro", ".toml"))
        if source or resource or manifest or release or is_test_file(relative):
            reasons["test_quality"].append(relative)
        # Resource qualifiers include layout-land, values-ar, values-night etc.
        ui_resource = bool(re.search(r"(?:^|/)res/(?:layout|navigation|menu|values|drawable|font|color)(?:-[^/]+)?/", lower))
        ui_source = source and not is_test_file(relative) and bool(UI_CODE.search(source_versions(repo, relative)))
        if ui_resource or ui_source:
            reasons["ui_expert"].append(relative)
    from _review_policy import additions
    for key, triggers in additions(repo, paths).items():
        reasons[key].extend(triggers)
    return {
        "required_reviewers": LEAF_KEYS + [key for key, files in reasons.items() if files],
        "reasons": {key: files for key, files in reasons.items() if files},
        "cosmetic_candidates_advisory_only": cosmetic_candidates,
        "classification": "conservative heuristic; inspect the competency matrix for additional risks",
    }
