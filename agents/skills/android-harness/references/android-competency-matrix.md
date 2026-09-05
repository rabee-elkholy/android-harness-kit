# Android competency and verification matrix

Read the rows relevant to the diff and its callers before implementation. These
are investigation prompts, not claims of exhaustive coverage or fixed architecture.

## Lead agent contract

1. Establish actual modules/source sets, supported SDKs, build variants, UI toolkit,
   DI, state ownership, persistence, supported locales and test infrastructure from
   this checkout. Distinguish discovered facts from setup stubs and assumptions.
2. Map the changed behavior and callers to the rows below. Read the corresponding
   project reference; verify version-sensitive APIs against official documentation.
3. Preserve the project's architecture and user authorization. Do not add a library,
   locale, annotation or redesign merely to satisfy a generic preference.
4. Select concrete failure scenarios and expected outcomes before implementation.
   Record each applicable row as VERIFIED (with evidence), NOT_APPLICABLE (reason),
   or BLOCKED (missing environment/evidence). A source review is not a device test.
5. Include this assessment in the review report summary and final delivery. Missing
   evidence for an applicable critical behavior blocks a claim of verified delivery.
   The matrix is a reviewer obligation; the runtime does not infer or validate these
   semantic statuses. Do not confuse passing the gate with complete Android coverage.

## Ownership and evidence

| Surface | Review owner(s) | Required investigation and relevant evidence |
| --- | --- | --- |
| State, lifecycle, navigation | bug + regression | Recreation versus process death; saved state and durable data ownership; back stack/deep links; duplicate events; restoration scenario with expected state. Activity recreation alone is not process-death evidence. |
| Coroutines, Flow, concurrency | bug + performance + test | Cancellation propagation, scope lifetime, collectors, concurrent requests, dispatchers and races; deterministic tests exercising the real production path. |
| Compose and XML UI | UI + convention | State observation, effect keys, binding lifetime, list identity, adaptive layouts, insets/IME; meaningful interaction and restoration checks. Stability annotations require a valid contract, not blanket application. |
| Accessibility and localization | UI + convention | Supported locales, RTL when applicable, font scaling, semantics, focus and TalkBack task completion; automated checks plus relevant device observations. |
| Room and persistence | convention + regression + test | Schema versus non-schema change, supported upgrade paths, preserved data, transactions and rollback; migration tests on populated old schemas. Creating a fresh database is not migration evidence. |
| Network, cache, paging, sync | bug + regression + test | Offline, timeout, malformed payload, retry/idempotency, stale cache, auth expiry, pagination boundaries; contract tests and recovery scenarios. |
| Background work and platform services | performance + security + regression | Lifecycle ownership, permission denial/revocation, scheduling, foreground/background transitions, resource release; supported API/device scenarios. Verify platform-version rules before prescribing changes. |
| Security, storage, IPC | security + bug | Exported components, untrusted intents/URIs, deep-link auth, secret handling, storage and network trust boundaries; abuse-case tests and manifest inspection. |
| Build, dependencies, release | convention + security + regression + test | Actual variants/source sets, manifest merging, dependency compatibility, R8/reflection/serialization, signing configuration; affected release build and release-only behavior checks, without exposing secrets. |
| KMP and native boundaries | convention + bug + test | common/platform source sets, expect/actual behavior, iOS interop, cancellation and ownership; common tests plus affected target compile/tests. Android success does not establish iOS success. |
| Purchases and subscriptions | security + regression + test | Pending/cancelled/duplicate purchases, restore, account switch, entitlement authority and retry; sandbox scenarios against the actual integration contract. |
| Runtime performance | performance + QA diagnostics as needed | Startup, frame times, memory retention, ANR and battery hypotheses; before/after measurements under comparable conditions. No universal FPS or zero-regression guarantees. |

## Automatic routing and its limits

`review_package.py` prints REQUIRED_REVIEWERS and ANDROID_REVIEW_SCOPE. Five base
reviewers remain required. Test quality is also required for Kotlin/Java, build
scripts, Android resources/manifests, ProGuard/TOML configuration and test paths,
even when no test changed. UI review is required for UI resource directories and
source containing Compose/View signals in either HEAD or the working tree.
Deleted files and removed annotations therefore still activate review.

Routing is conservative and heuristic: comments can activate it, and indirect UI
wrappers, generated code and unusual frameworks can evade detection. The lead must
add a specialist when the semantic impact requires it. QA diagnostics remains
on-demand. Use one dispatch when capacity permits; otherwise use bounded batches
against the same package and collect every required report before proceeding.

## Official reference starting points

- [Compose stability contracts](https://developer.android.com/develop/ui/compose/performance/stability/fix)
- [Saving UI state](https://developer.android.com/topic/libraries/architecture/saving-states)
- [Accessibility testing](https://developer.android.com/guide/topics/ui/accessibility/testing)

Verify references against the versions used by the client. These links are not
substitutes for observed runtime behavior.
