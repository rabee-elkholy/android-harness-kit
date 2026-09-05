# Delivery evidence contract (unreleased)

This update changes the evidence schema, not the published package version.
Do not reuse v0.27.12 verdicts. No new tag or PyPI release is created by this change.

## Identity and state

A snapshot hashes checkout input bytes, HEAD, Git changes/modes and installed
engine/policy files. Build outputs and runtime state are excluded. Files added,
deleted or renamed, resources, catalogs and Groovy build files are covered.
Unreadable inputs, unresolved conflicts and external symlinks fail verification.
Submodules currently require explicit support and fail with a diagnostic.

Set `HARNESS_TASK_ID` consistently for every command in a task. The default is a
single local task; use explicit IDs for simultaneous sessions. Results live under
`agents/state/tasks/<task-key>/` (or `.agents/state/tasks/<task-key>/` in clients).
A gate marks its run RUNNING first. Newer runs supersede older runs. Content
changes during a run produce STALE, not PASS. OS locks protect concurrent writers
and atomic replacement prevents partially written JSON from looking valid.

The snapshot is deliberately conservative. Documentation or staging changes can
invalidate evidence. Fine-grained reuse is deferred until independently validated.
Host tools, Gradle properties outside the checkout and remote dependency contents
are not fully hermetic; CI should pin dependencies and rerun checks independently.

## Test gate and baseline

Always run `python .agents/scripts/run_tests_gate.py`. A raw successful Gradle
artifact is not a substitute for parsed test reports. The gate clears only its
expected `TEST-*.xml` outputs and reruns the specified test task without the build
cache to prevent historical report reuse. Custom build directories/report layouts
are not inferred: configure or extend the adapter before treating them as covered.
No reports, malformed XML, all-skipped or NO-SOURCE is incomplete verification.

Capture a baseline on a clean checkout with
`python .agents/scripts/baseline_capture.py --run-tests`. Capture always executes
its task; `--run-tests` remains a compatibility spelling. Refresh needs explicit
developer authorization and `--approve`. Baselines are schema 2 and distinguish
Gradle task, testcase and failure signature. Legacy baselines require recapture;
a new failure in a previously failing test is not automatically ignored.

## Reviews

Generate a complete package with `review_package.py`. Record each leaf using:

```sh
python .agents/scripts/record_review.py --pkg <package-hash> --leaf bug --verdict BUG_PASS --report <report.json>
```

A report has this shape (use actual values and findings):

```json
{
  "package_hash": "full-package-sha256",
  "snapshot_id": "snapshot-from-package-record",
  "summary": "Concrete review scope and conclusion",
  "reviewed_files": ["app/src/main/java/example/Feature.kt"],
  "findings": []
}
```

Repeat for the five roles, plus test quality when the changed paths include tests.
Use verdict `FAIL` and findings to revoke a previous pass. Bulk approval and
free-text token parsing are refused. Partial/truncated packages cannot approve
whole-checkout delivery. Reports are self-reported unless a native transcript
provides provenance; neither case proves review quality cryptographically.

## Device verification

Build with `run_gradle_task.py`, then `run_device.py install-start`. The install
must match the recorded APK digest and build run. `--force` is not a delivery path.
Uninstall is maintenance, never verification. Launch success does not prove a
scenario passed, and crash observation is not inferred from an ADB return code.

After actually checking the scenario, provide a JSON report:

```json
{
  "serial": "the-observed-device",
  "apk_sha256": "digest-from-install-artifact",
  "result": "PASS",
  "steps": [{"action": "Open the changed screen", "expected": "Expected state", "observed": "Actual state", "passed": true}]
}
```

Run `record_device_verification.py --kind smoke --report <report.json>`.
Manual mode also needs `--kind manual`, run in the developer's terminal with
interactive PASS/FAIL confirmation. The terminal is a local attestation, not
proof of human identity against an agent with terminal control. Autonomous mode
requires an actual executed scenario report; the harness does not invent E2E
coverage from installation. Reinstalling invalidates prior scenario reports.
Keep reports in runtime state so authoring the report does not change app inputs.

## Verification, updates and trust

`android-harness verify` and `final_verdict.py` use the same validator. A review-only
`--verdict` is refused. `verify --rerun-checks` reruns preflight; it does not claim
that tests, builds or device scenarios have also been rerun. Exit 0 means APPROVED,
30 means an environment block, and 1 means blocked/stale/incomplete evidence.

Engine updates stage files before replacing the active engine, retain recovery
copies until validation succeeds and preserve baseline debt. A failed or interrupted
update restores prior managed files. Legacy delivery evidence must be regenerated.
Backups are retained for explicit inspection/cleanup rather than deleted before
a new backup is complete. Recovery cannot protect unrelated concurrent edits made
by another process outside the harness update lock.

The local agent and developer can write the engine and records. This is an error
prevention and evidence system, not an OS sandbox or tamper-proof approval service.
Independent CI checks the exact release SHA and package bytes before publication.

## Remaining validation

Python suites and distribution tests can run without Android. The SDK-equipped
CI job performs an actual Room v1-to-v2 migration and preserved-data assertions.
Its remote result is required before claiming Android integration passed. This is
one fixture, not evidence of compatibility with every Android/KMP project. Broader
KMP, product profiles and comparative benchmarks remain follow-up work.
