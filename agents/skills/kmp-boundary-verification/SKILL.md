---
name: kmp-boundary-verification
description: Review and verify Kotlin Multiplatform source-set and platform-boundary changes affecting common code, expect/actual or native interop; not Android-only edits with no shared impact.
---

# KMP boundary verification

Read the real target and source-set hierarchy, dependency graph and existing test
configuration. Do not infer supported targets from directory names alone.

1. Trace changed common contracts to platform implementations and callers. Include
   expect/actual behavior, error mapping, cancellation, platform resources and data
   ownership crossing native interop. Preserve the project's abstractions.
2. Select common tests and the affected target compile/tests using discovered tasks.
   Use the harness Gradle wrapper where applicable; native/Xcode validation follows
   the existing project toolchain. Do not invent target names or install a new stack.
3. Check platform-specific implementations against the same contract, including
   unavailable platform services, failure propagation and lifecycle/resource cleanup.
   Passing common tests does not establish native integration correctness.
4. Record per-target evidence and status. If an iOS change cannot run on the current
   host, report that target BLOCKED and provide the exact remaining validation task.
   Android success cannot be reported as iOS success. Do not rewrite platform code
   merely to make an unsupported host pass.

Use scenario checks to link current successful artifacts where available; document
native evidence separately when no compatible gate artifact exists. Hashes establish
freshness, not cross-platform equivalence. Follow the canonical review-delivery
workflow and invoke extra specialists only for actual semantic impact.
