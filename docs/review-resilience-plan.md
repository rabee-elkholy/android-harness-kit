# Review resilience and focused Android verification

Branch: `fix/evidence-integrity-and-release-gates`; base for this increment: f795c49.

## Changes and acceptance criteria

1. Add snapshot-bound, additive reviewer policy for indirect UI/custom modules.
   No rule may remove a base or detected specialist. Invalid policy fails closed.
   Comment/format candidates are advisory only: do not reduce gates using a lexer.
2. Permit bounded native review batches for current evidence packages. Keep the
   legacy single-call route compatible. Count one round per package, reject mixed
   packages and duplicate dispatch, preserve reports, and block delivery until
   all required structured reports exist. Reject stale packages between batches.
3. Add optional structured scenario checks with hashed, current gate artifacts.
   VERIFIED checks require matching successful evidence; BLOCKED cannot PASS.
   Revalidate referenced artifacts at final verdict. Reports without these checks
   remain self-reported; no claim of independent reviewer identity is introduced.
4. Consolidate current delivery instructions in one installed workflow. Remove
   conflicting fixed-count/single-call requirements from active entrypoints and
   route them to the workflow. Preserve unrelated architecture and user policies.
5. Add narrowly triggered lifecycle, release and KMP verification skills. They
   select actual project targets/scenarios, report unavailable environments, and
   never infer iOS/release/process-death success from Android debug/recreation.
6. Validate adversarial batch/policy/artifact cases, full kit regressions, skill
   structure and distribution installation. Commit on the existing branch.

## Stability boundaries

Use additive configuration with absent-policy behavior unchanged. Do not introduce
dependencies, automatic Gradle rewrites, a new agent roster, permissive evidence
fallbacks, or unverified semantic filtering. Full Android application trials and
blind model evaluations remain separate environment-dependent work. Python kit
development does not run Android reviewer agents.

The target is demonstrably reduced risk, not a promise of zero new defects. A
follow-up can be reverted independently of earlier evidence-integrity repairs.

## Additional update compatibility repair

An upgrade previously deleted newly shipped reference guides when restoring any
custom references. Installation now overlays custom files onto new defaults and
preserves the validated additive policy. Invalid policy aborts before swapping
the existing engine. Existing rollback behavior is retained and tested.

## Completed validation

All 16 self-test suites and the root regression suite passed. The resilience suite
passed 44 tests (including inherited evidence-integrity cases), and installer
transaction coverage passed 6 tests. The four affected/new skills passed structural
validation. Fresh wheel and sdist builds both passed installation outside the
checkout, including the new modules, workflow, skills and client setup.

No Android reviewer agents were launched for kit development. No live Android/iOS
scenario or blind model benchmark was executed. Cosmetic detection remains advisory
and all existing review requirements remain conservative.
