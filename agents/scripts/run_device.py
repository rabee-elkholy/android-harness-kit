"""Physical-device install/launch with a live adb task log.

Usage:
  python .agents/scripts/run_device.py install
  python .agents/scripts/run_device.py start
  python .agents/scripts/run_device.py install-start
  python .agents/scripts/run_device.py uninstall
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _apk_freshness import check_apk_freshness, format_freshness_error  # noqa: E402
from _env_codes import (  # noqa: E402
    CLASS_ENV,
    EXIT_ENV,
    FailureVerdict,
    classify_adb_failure,
    emit_env_failure,
    exit_for,
    no_device_verdict,
)
from _gate_results import current_head_sha, write_gate_result, GateRun, read_gate_result  # noqa: E402
from _live_process import enable_line_buffered_stdio, live_print, run_streaming  # noqa: E402
from _product import (  # noqa: E402
    ALLOW_EMULATOR,
    APPLICATION_ID,
    ASSEMBLE_TASK,
    LAUNCHER,
    PRODUCT_NAME,
)
from _repo_files import REPO, first_adb_serial  # noqa: E402
from _variants import apk_relative, resolve_or_raise  # noqa: E402

DEFAULT_ACTIVITY = LAUNCHER
_ACTIVE_RUNS: dict = {}
_BINDING: dict = {}


def record_device(action: str, status: str, exit_code: int, serial: str | None, env_class: str = "", detail: str = "") -> None:
    if action == "require-serial":
        for active in _ACTIVE_RUNS.values():
            active.finish({"status": status, "exit_code": exit_code, "env_class": env_class, "detail": detail})
    name = {"install": "device_install", "start": "device_launch"}.get(action, "device_maintenance")
    run = _ACTIVE_RUNS.get(name) or GateRun(name)
    result = run.finish({
        **_BINDING, "action": action, "status": status, "exit_code": exit_code,
        "env_class": env_class, "serial": serial, "application_id": APPLICATION_ID, "detail": detail,
    })
    if status == "PASS" and result["status"] != "PASS":
        raise RuntimeError(result["detail"])


def require_serial(explicit: str | None) -> str:
    allow_emu = bool(ALLOW_EMULATOR)
    serial = explicit or first_adb_serial(allow_emulator=allow_emu)
    if not serial:
        verdict = no_device_verdict()
        record_device("require-serial", "ENV", EXIT_ENV, serial, verdict.env_class, verdict.reason)
        emit_env_failure(verdict, "run_device.py")
        sys.exit(EXIT_ENV)
    if not allow_emu and serial.startswith("emulator-"):
        verdict = FailureVerdict(
            CLASS_ENV,
            "Emulator targeting is forbidden by project policy. Connect a physical device.",
        )
        record_device("require-serial", "ENV", EXIT_ENV, serial, verdict.env_class, verdict.reason)
        emit_env_failure(verdict, "run_device.py", serial=serial)
        sys.exit(EXIT_ENV)
    return serial



def run_adb(serial: str, adb_args: list[str], label: str) -> tuple[int, str]:
    live_print(f"[*] adb -s {serial} {' '.join(adb_args)}")
    code, log, _ = run_streaming(
        ["adb", "-s", serial, *adb_args],
        cwd=str(REPO),
        heartbeat_sec=10.0,
        should_echo=lambda line: bool(line.strip()),
        label=label,
    )
    return code, log


def main() -> int:
    enable_line_buffered_stdio()
    parser = argparse.ArgumentParser(description=f"Live adb install/start for {PRODUCT_NAME}")
    parser.add_argument("action", choices=["install", "start", "install-start", "uninstall"])
    parser.add_argument("-s", "--serial", default=None, help="Physical device serial")
    parser.add_argument(
        "--flavor",
        default=None,
        help="Build flavor for APK resolution (default: ACTIVE_FLAVOR in _product.py).",
    )
    parser.add_argument("--apk", default=None, help="Debug APK path (overrides --flavor resolution)")
    parser.add_argument("--activity", default=DEFAULT_ACTIVITY, help="Launch activity")
    parser.add_argument("--package", default=APPLICATION_ID, help="Package name to uninstall")
    parser.add_argument("--user", default=None, help="Target user ID for multi-user / work profile devices (e.g. 0)")
    parser.add_argument("--force", action="store_true", help="Bypass APK freshness check (emergency manual use only)")
    args = parser.parse_args()
    _ACTIVE_RUNS.clear()
    _BINDING.clear()
    if args.action in ("install", "install-start"):
        _ACTIVE_RUNS["device_install"] = GateRun("device_install")
    if args.action in ("start", "install-start"):
        _ACTIVE_RUNS["device_launch"] = GateRun("device_launch")

    try:
        active_flavor, _task = resolve_or_raise(args.flavor)
    except SystemExit as exc:
        live_print(str(exc), err=True)
        return 1

    apk = Path(args.apk) if args.apk else REPO / apk_relative(active_flavor)
    variant_note = f" (variant: {active_flavor})" if active_flavor else ""
    serial = require_serial(args.serial)
    live_print(f"[*] Physical device{variant_note}: {serial}")

    if args.action == "uninstall":
        live_print(f"[*] Uninstalling {args.package} from {serial}")
        code, log = run_adb(serial, ["uninstall", args.package], "adb uninstall")
        if code != 0:
            verdict = classify_adb_failure(code, log)
            live_print(f"[!] adb uninstall failed (exit {code})", err=True)
            record_device(args.action, "ENV" if verdict.env_class != "CODE" else "FAIL", exit_for(verdict), serial, verdict.env_class, verdict.reason)
            emit_env_failure(verdict, "run_device.py", serial=serial)
            return exit_for(verdict)
        record_device(args.action, "PASS", 0, serial)
        if args.package == APPLICATION_ID:
            GateRun("device_install").finish({"status": "FAIL", "exit_code": 1, "detail": "Application was uninstalled; install and verify again"})
        live_print(f"[+] Uninstall finished for {args.package}")
        return 0

    if args.action in ("install", "install-start"):
        if args.force:
            live_print("[FAIL] --force is not accepted for delivery; rebuild the current inputs", err=True)
            return 1
        try:
            from _device_evidence import current_build
            from _variants import assemble_task
            _BINDING.update(current_build(apk, assemble_task(active_flavor)))
        except (ValueError, OSError, RuntimeError) as exc:
            record_device("install", "FAIL", 1, serial, detail=str(exc))
            return 1
        if not args.force:
            freshness = check_apk_freshness(apk, REPO, active_flavor)
            if not freshness.is_fresh:
                live_print(format_freshness_error(freshness, apk, active_flavor), err=True)
                if freshness.status == "MISSING_APK":
                    verdict = FailureVerdict(
                        CLASS_ENV,
                        f"APK not found: {apk} (pipeline order: assemble before install)",
                    )
                    record_device("install", "ENV", EXIT_ENV, serial, verdict.env_class, verdict.reason)
                    emit_env_failure(verdict, "run_device.py", serial=serial)
                    return EXIT_ENV
                else:
                    record_device("install", "FAIL", 1, serial, "CODE", freshness.reason)
                    return 1
        elif not apk.is_file():
            live_print(f"[ERROR] APK not found: {apk}", err=True)
            live_print(f"Assemble debug first: python .agents/scripts/run_gradle_task.py {ASSEMBLE_TASK}", err=True)
            verdict = FailureVerdict(
                CLASS_ENV,
                f"APK not found: {apk} (pipeline order: assemble before install)",
            )
            record_device("install", "ENV", EXIT_ENV, serial, verdict.env_class, verdict.reason)
            emit_env_failure(verdict, "run_device.py", serial=serial)
            return EXIT_ENV
        size_mb = apk.stat().st_size / (1024 * 1024)
        live_print(f"[*] Installing {apk.as_posix()} ({size_mb:.1f} MB)")
        install_cmd = ["install", "-r", "-d", "-g"]
        if args.user is not None:
            install_cmd.extend(["--user", str(args.user)])
        install_cmd.append(str(apk))
        code, log = run_adb(serial, install_cmd, "adb install")
        if code != 0:
            verdict = classify_adb_failure(code, log)
            live_print(f"[!] adb install failed (exit {code})", err=True)
            record_device("install", "ENV" if verdict.env_class != "CODE" else "FAIL", exit_for(verdict), serial, verdict.env_class, verdict.reason)
            emit_env_failure(verdict, "run_device.py", serial=serial)
            return exit_for(verdict)
        record_device("install", "PASS", 0, serial)
        live_print("[+] Install finished")

    if args.action in ("start", "install-start"):
        from _evidence import context, matches
        installed = read_gate_result("device_install") or {}
        if not matches(installed, context()) or installed.get("status") != "PASS" or installed.get("serial") != serial:
            record_device("start", "FAIL", 1, serial, detail="No matching current installation")
            return 1
        _BINDING.update({k: installed[k] for k in ("apk_sha256", "apk_path", "build_run_id")})
        _BINDING["install_run_id"] = installed["run_id"]
        target_activity = args.activity
        if "/" not in target_activity:
            target_activity = (
                f"{APPLICATION_ID}/{target_activity if target_activity.startswith('.') else '.' + target_activity}"
            )
        live_print(f"[*] Launching target Activity: {target_activity}")
        code, log = run_adb(
            serial,
            ["shell", "am", "start", "-n", target_activity],
            "am start",
        )
        if code != 0 or __import__("re").search(r"(?im)^Error(?: type|:)|Exception", log):
            code = code or 1
            verdict = classify_adb_failure(code, log)
            live_print(f"[!] am start failed (exit {code})", err=True)
            record_device("start", "ENV" if verdict.env_class != "CODE" else "FAIL", exit_for(verdict), serial, verdict.env_class, verdict.reason)
            emit_env_failure(verdict, "run_device.py", serial=serial)
            return exit_for(verdict)
        record_device("start", "PASS", 0, serial)
        live_print(f"[+] Launched {target_activity}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
