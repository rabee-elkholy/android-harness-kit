"""Canonical reviewer vocabulary and package validation."""
from pathlib import Path

LEAF_KEYS = [
    "bug_reviewer",
    "convention_reviewer",
    "security_reviewer",
    "perf_guardian",
    "regression_reviewer",
]

LEAF_PASS_VALUES = {
    "bug_reviewer": "BUG_PASS",
    "convention_reviewer": "CONVENTION_PASS",
    "security_reviewer": "SECURITY_PASS",
    "perf_guardian": "PERF_PASS",
    "regression_reviewer": "REGRESSION_PASS",
    "test_quality": "TEST_PASS",
}

LEAF_ALIASES = {
    "bug_reviewer": ("bug_reviewer", "bug-reviewer-agent", "bug-reviewer", "bug"),
    "convention_reviewer": ("convention_reviewer", "convention-reviewer-agent", "convention-reviewer", "convention"),
    "security_reviewer": ("security_reviewer", "security-reviewer-agent", "security-reviewer", "security"),
    "perf_guardian": ("perf_guardian", "perf-anr-guardian-agent", "perf-anr-guardian", "perf"),
    "regression_reviewer": ("regression_reviewer", "regression-impact-reviewer-agent", "regression-impact-reviewer", "regression"),
    "test_quality": ("test_quality", "test-quality-reviewer-agent", "test-quality-reviewer", "test_quality_reviewer", "test"),
}


def required_keys(record: dict) -> list[str]:
    from _snapshot import capture
    from _repo_files import REPO
    changed = capture(REPO)["changes"]
    return LEAF_KEYS + (["test_quality"] if any(is_test_file(e["path"]) for e in changed) else [])


def package_valid(record: dict) -> bool:
    from _evidence import context, matches
    from _snapshot import file_digest
    from _repo_files import REPO
    if not matches(record, context()) or record.get("is_truncated") or record.get("partial"):
        return False
    pkg = record.get("package") or {}
    path = Path(str(pkg.get("path") or ""))
    try:
        return path.is_file() and path.resolve().is_relative_to(REPO.resolve()) and file_digest(path, REPO) == pkg.get("sha256")
    except (OSError, RuntimeError):
        return False


def is_test_file(path_str: str) -> bool:
    p = path_str.replace("\\", "/").lower()
    return (
        "/test/" in p
        or "/androidtest/" in p
        or "/sharedtest/" in p
        or p.endswith("test.kt")
        or p.endswith("tests.kt")
        or p.endswith("test.java")
        or p.endswith("tests.java")
    )

