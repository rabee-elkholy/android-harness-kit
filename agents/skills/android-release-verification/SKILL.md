---
name: android-release-verification
description: Select and verify affected Android build variants, manifests and release behavior when Gradle, dependencies, shrinking, reflection or packaging changes; not routine UI-only review.
---

# Build and release verification

Discover the actual build modules, variants, source sets, plugin/dependency versions
and supported delivery target. Use project configuration and Gradle task discovery;
never assume an app module or a universal assembleRelease task.

1. Map changed build logic, dependency declarations, manifest fragments, keep rules
   and serialization/reflection code to affected consumers and variants. Shared build
   logic can affect multiple modules even if only one script changed.
2. Choose an affected production variant and relevant tests. Run tasks through the
   harness Gradle wrapper. Keep signing credentials private; missing credentials are
   an environment limitation, not a reason to rewrite signing or disable shrinking.
3. Inspect the merged manifest and relevant packaged resources/dependencies for that
   variant. Check that the tested artifact is the one produced by that run.
4. Where reflection, serialization, native libraries or dynamic loading are involved,
   exercise those behaviors on the actual minified/release-equivalent artifact.
   Debug compilation cannot prove that shrinking retained required behavior.
5. Record module, exact task/variant, artifact digest, environment and runtime cases.
   State explicitly which other variants were not built. Do not claim release-ready
   based on a debug-only test or placeholder signing configuration.

Use VERIFIED/NOT_APPLICABLE/BLOCKED with evidence. Select meaningful tests rather
than building every variant indiscriminately. Do not publish, sign with new keys or
change release configuration without the authorization required by the project.
Use the canonical review-delivery workflow for current evidence recording.
