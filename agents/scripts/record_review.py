"""Universal Review Verdict Recorder for Android Agent Harness.

Enables agents in non-Antigravity environments (OpenAI Codex, Claude Code,
Cursor) to record review verdicts into the harness verdict ledger so that
final_verdict.py passes with 100% parity across all tools.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_state import (
    read_verdict_record,
    state_path,
    tree_code_fingerprint,
    write_verdict_record,
)
from _live_process import enable_line_buffered_stdio, live_print

enable_line_buffered_stdio()

LEAF_NAME_MAP = {
    "bug-reviewer-agent": "bug_reviewer",
    "bug_reviewer": "bug_reviewer",
    "bug": "bug_reviewer",
    "convention-reviewer-agent": "convention_reviewer",
    "convention_reviewer": "convention_reviewer",
    "convention": "convention_reviewer",
    "security-reviewer-agent": "security_reviewer",
    "security_reviewer": "security_reviewer",
    "security": "security_reviewer",
    "perf-anr-guardian-agent": "perf_guardian",
    "perf_guardian": "perf_guardian",
    "perf_anr_guardian": "perf_guardian",
    "perf": "perf_guardian",
    "regression-impact-reviewer-agent": "regression_reviewer",
    "regression_reviewer": "regression_reviewer",
    "regression_impact": "regression_reviewer",
    "regression": "regression_reviewer",
    "test-quality-reviewer-agent": "test_quality",
    "test_quality": "test_quality",
    "test": "test_quality",
}

PASS_TOKENS = {
    "bug_reviewer": "BUG_PASS",
    "convention_reviewer": "CONVENTION_PASS",
    "security_reviewer": "SECURITY_PASS",
    "perf_guardian": "PERF_PASS",
    "regression_reviewer": "REGRESSION_PASS",
    "test_quality": "TEST_PASS",
}


def get_latest_pkg12() -> str | None:
    ledger_file = state_path().parent / "review_ledger.json"
    if not ledger_file.is_file():
        return None
    try:
        data = json.loads(ledger_file.read_text(encoding="utf-8"))
        sha = str(data.get("sha256") or "")
        return sha[:12] if len(sha) >= 12 else None
    except Exception:
        return None


def record_leaf_verdict(
    pkg12: str,
    leaf_canonical: str,
    verdict: str,
    cites: int = 1,
    findings: list[str] | None = None,
    report: dict | None = None,
) -> bool:
    from _review_contract import package_valid, required_keys
    from _evidence import locked
    with locked(state_path().parent / ("record-" + pkg12 + ".lock")):
        record = read_verdict_record(pkg12)
        if not record or not package_valid(record):
            live_print("[REFUSED] Missing, stale or incomplete review package", err=True)
            return False
        if not report or not isinstance(report.get("summary"), str) or not report["summary"].strip():
            live_print("[REFUSED] A structured reviewer report is required", err=True)
            return False
        if report.get("package_hash") != record["package"]["sha256"] or report.get("snapshot_id") != record["snapshot_id"]:
            return False
        supplied_findings = report.get("findings", [])
        if not isinstance(supplied_findings, list) or not all(isinstance(f, str) and f.strip() for f in supplied_findings):
            return False
        report = dict(report, findings=supplied_findings + list(findings or []))
        reviewed = report.get("reviewed_files")
        if not isinstance(reviewed, list) or not reviewed or not all(isinstance(f, str) and f in record.get("files", {}) for f in reviewed):
            return False
        if verdict not in (PASS_TOKENS[leaf_canonical], "FAIL"):
            return False
        leaves = record.setdefault("leaves", {})
        leaves[leaf_canonical] = {"verdict": verdict, "token": verdict, "report": report,
                                  "attestation": "self_reported", "recorded_at": time.time()}
        record["findings"] = [f for leaf in leaves.values() for f in leaf.get("report", {}).get("findings", [])]
        required = required_keys(record)
        all_passed = not record["findings"] and all(leaves.get(k, {}).get("token") == PASS_TOKENS[k] for k in required)
        record["verdict"] = "APPROVED" if all_passed else "PENDING"
        record["completed_at"] = time.time() if all_passed else None
        return write_verdict_record(pkg12, record)


def approve_all_leaves(pkg12: str) -> bool:
    live_print("[REFUSED] Bulk approval cannot establish independent reviews; submit each structured --report", err=True)
    return False


def parse_and_record_text(pkg12: str, text: str) -> int:
    live_print("[REFUSED] Free-text PASS tokens are not review evidence; use --report", err=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Universal review verdict recorder.")
    parser.add_argument("--pkg", help="12-char package SHA256 digest (defaults to latest in ledger).")
    parser.add_argument("--approve-all", action="store_true", help="Record clean PASS for all required leaves.")
    parser.add_argument("--leaf", help="Leaf name (e.g. bug-reviewer-agent, security, perf, etc.).")
    parser.add_argument("--verdict", help="Verdict token (e.g. BUG_PASS, SECURITY_PASS, etc.).")
    parser.add_argument("--cites", type=int, default=1, help="Citations count.")
    parser.add_argument("--parse-text", help="Path to file or string containing review output.")
    parser.add_argument("--stdin", action="store_true", help="Read review output from stdin.")
    parser.add_argument("--report", type=Path, help="Structured JSON reviewer report")
    parser.add_argument("--finding", action="append", default=[], help="Finding description.")
    args = parser.parse_args(argv)

    raw_pkg = args.pkg or get_latest_pkg12()
    if not raw_pkg:
        live_print("[ERROR] Could not determine package digest. Run review_package.py first.", err=True)
        return 1

    candidate_file = Path(raw_pkg)
    if candidate_file.is_file():
        pkg12 = hashlib.sha256(candidate_file.read_bytes()).hexdigest()[:12]
    else:
        pkg12 = raw_pkg[:12]

    if not re.fullmatch(r"[0-9a-f]{12}", pkg12):
        live_print("[REFUSED] Invalid package digest", err=True)
        return 1

    if args.approve_all:
        ok = approve_all_leaves(pkg12)
        return 0 if ok else 1

    if args.stdin:
        text = sys.stdin.read()
        count = parse_and_record_text(pkg12, text)
        live_print(f"[*] Parsed and recorded {count} verdict(s) from stdin.")
        return 0 if count > 0 else 1

    if args.parse_text:
        path = Path(args.parse_text)
        content = path.read_text(encoding="utf-8") if path.is_file() else args.parse_text
        count = parse_and_record_text(pkg12, content)
        live_print(f"[*] Parsed and recorded {count} verdict(s).")
        return 0 if count > 0 else 1

    if args.leaf and args.verdict:
        leaf_canon = LEAF_NAME_MAP.get(args.leaf.strip().lower())
        if not leaf_canon:
            live_print(f"[ERROR] Unknown leaf name: '{args.leaf}'", err=True)
            return 1
        ok = record_leaf_verdict(pkg12, leaf_canon, args.verdict.strip(), args.cites, findings=args.finding,
                                 report=json.loads(args.report.read_text(encoding="utf-8")) if args.report else None)
        return 0 if ok else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
