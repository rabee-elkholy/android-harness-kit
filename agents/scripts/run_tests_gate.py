"""Unit-test delivery gate with baseline-aware regression classification.

Usage:
  python .agents/scripts/run_tests_gate.py

Runs the configured unit-test Gradle task, parses the JUnit XML reports, and
classifies every failure:

  NEW_REGRESSION    failed now and is absent from the baseline -> BLOCK (exit 1)
  BASELINE_IGNORED  failed now and is recorded in the baseline -> tolerated
                    (pre-existing debt, never reported as a regression)

Writes the `unit_tests` gate artifact consumed by final_verdict.py. When the
Gradle run fails environmentally, the exit-30 protocol applies unchanged.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baseline_capture import (  # noqa: E402
    collect_failures,
    load_baseline,
)
from _env_codes import EXIT_ENV  # noqa: E402
from _gate_results import current_head_sha, write_gate_result  # noqa: E402
from _live_process import enable_line_buffered_stdio, live_print  # noqa: E402
from _repo_files import REPO  # noqa: E402


def baseline_advisory(baseline: dict | None, head: str) -> str:
    if not baseline:
        return ""
    baseline_commit = str(baseline.get("baseline_commit") or "")
    if not baseline_commit or not head:
        return ""
    if baseline_commit == head:
        return ""
    return (
        f"[!] BASELINE ADVISORY: baseline was captured at {baseline_commit[:12]}, "
        f"current HEAD is {head[:12]}. Pre-existing debt is still honored; "
        "refresh the baseline (clean tree + --approve) only when the developer asks."
    )


def classify_failures(failed: list[dict], baseline: dict | None) -> tuple[list[dict], list[dict], int]:
    if not baseline:
        return list(failed), [], 0
    known = {str(item.get("fingerprint") or "") for item in (baseline.get("unit_tests") or []) if item.get("fingerprint")}
    new_regressions: list[dict] = []
    ignored: list[dict] = []
    for item in failed:
        if item.get("fingerprint") in known:
            ignored.append(item)
        else:
            new_regressions.append(item)
    return new_regressions, ignored, len(known)


def main(argv=None) -> int:
    enable_line_buffered_stdio()
    parser = argparse.ArgumentParser(description="Baseline-aware unit-test delivery gate")
    parser.add_argument("task", nargs="?", default=None, help="Gradle unit-test task (default: _product UNIT_TEST_TASK)")
    args = parser.parse_args(argv)

    from baseline_capture import _unit_test_task
    from _gate_results import GateRun
    from _test_reports import execute_tests
    import xml.etree.ElementTree as ET
    task = args.task or _unit_test_task()
    gate = GateRun("unit_tests")
    try:
        code, run, reports = execute_tests(REPO, task)
        if not reports:
            gate.finish({"status": "ENV" if code == EXIT_ENV else "FAIL", "exit_code": code,
                         "task": task, "detail": run.get("detail", "Test execution incomplete")})
            return code or 1
        baseline = load_baseline()
        if baseline and baseline.get("schema_version") != 2:
            raise ValueError("Legacy baseline must be recaptured on a clean checkout with --approve")
        new, ignored, _ = classify_failures(reports["failures"], baseline)
        result = gate.finish({"status": "FAIL" if new else "PASS", "exit_code": 1 if new else 0,
                              "task": task, "detail": f"{len(new)} NEW_REGRESSION; {len(ignored)} BASELINE_IGNORED",
                              "baseline_ignored": len(ignored), "reports": reports})
        live_print(result["detail"])
        return result["exit_code"]
    except (ValueError, OSError, RuntimeError, ET.ParseError) as exc:
        gate.finish({"status": "FAIL", "exit_code": 1, "task": task, "detail": str(exc)})
        live_print(f"[FAIL] {exc}", err=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
