# Android expertise and reviewer coverage improvements

Branch: `fix/evidence-integrity-and-release-gates`. Builds on the earlier evidence,
baseline, device, installer and release-gate repairs. No Android app reviewers are
invoked while developing this Python kit. The maintainer authorized implementation
and one combined branch push; no package release or default-branch merge is implied.

## Implementation and acceptance

1. **Lead-agent competency contract**: add a selectively loaded matrix covering
   lifecycle/process death, concurrency, UI/accessibility, persistence, network,
   background services, security, build/release, KMP, billing and measured performance.
   Acceptance: every row names review ownership, failure scenarios and concrete evidence;
   unverified scenarios cannot be described as verified.
2. **Automatic specialist routing**: require test-quality review for production,
   build and Android resource changes even without tests in the diff; activate UI
   review for detected UI sources and resources. Inspect current and HEAD content.
   Acceptance: additions, deletions, removed annotations, qualifiers and KMP tests
   have regression fixtures; Python kit/docs changes do not activate specialists.
3. **One enforceable reviewer contract**: align package headers, per-leaf recording,
   final verdict and native hook with dynamic requirements including UI_PASS.
   Acceptance: missing test/UI reports block approval; valid current reports complete
   the gate; stale evidence still fails. Old count fields cannot remove requirements.
4. **Prompt calibration**: remove blanket state annotations, mandatory Arabic for
   every project, assertion quotas and misleading performance guarantees in touched
   reviewer guidance. Explain limits and record evidence in reports.
   Acceptance: retain project-specific conventions and real test behavior; no new
   library or architecture is required solely to satisfy generic preferences.
5. **Verification and distribution**: run all kit self-tests, validate the revised
   skill, build and install wheel/sdist so the matrix and routing ship to clients.
   Commit the changes on the existing branch and attempt one combined push.

## Evaluation protocol for subsequent client trials

Routing tests measure routing correctness, not Android expertise. Before assigning
a numeric expertise score, evaluate the same base model with/without the harness
on blind, paired buggy/correct Android changes. Include lifecycle restoration,
coroutine cancellation, Room data-preserving upgrades, inaccessible interactions,
release-only serialization and KMP platform boundaries. Keep expected findings
hidden from the reviewing agent. Record model/version, prompt version, project
commit, device/API/variant, findings and execution evidence for each case.

Report confirmed defects detected / known defects, false findings / all findings,
missed critical defects, task completion rate, wall time and token cost separately.
Use multiple projects and repeated runs; publish raw denominators and environment
limitations. Do not equate a larger reviewer roster with independent expertise.

This implementation provides the contract and routing; it does not claim a completed
Android model benchmark, device matrix or iOS validation. Those require actual
client projects and their execution environments.

## Local implementation result

Steps 1–4 are implemented. Verification passed: all 15 self-test suites plus the
root regression suite; the final delivery suite separately passed 30 tests after
adding native-hook parity coverage. The revised skill validates. Both wheel and
sdist were built, installed outside the checkout, and used to install the new
routing module and competency matrix into a fixture client. No Android device,
iOS run or blind model benchmark was performed. Git upload is a separate transport
step and requires repository write access.
