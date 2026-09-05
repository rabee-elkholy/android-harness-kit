---
description: Canonical current delivery review, batching and evidence workflow for installed Android clients.
---

# Delivery review contract

This workflow defines reviewer execution referenced by harness-rules.md. It applies
in Android client checkouts, not Python kit maintenance. User instructions retain
precedence. No model expertise, reviewer independence or runtime success is inferred
from a PASS count.

1. Run `python .agents/scripts/run_tests_gate.py` and diff lint before
   `python .agents/scripts/review_package.py`. Use its complete current package.
2. Read `REQUIRED_REVIEWERS` and `ANDROID_REVIEW_SCOPE`; follow every required role.
   Five base reviewers remain. Test/UI promotion is additive. For indirect UI or
   custom wrappers, set `.agents/review-policy.json` before regenerating the package:

   ```json
   {"version":1,"require":[],"paths":{"feature/shared-ui":["ui_expert"]}}
   ```

   Paths are exact checkout-relative files or directory prefixes, not globs.
   Only `ui_expert` and `test_quality` additions are accepted. Policy changes stale
   previous evidence. Cosmetic candidates are advisory; do not skip review/test gates.
3. Dispatch one group when capacity permits. On current schema-v3 packages, native
   hooks also accept disjoint subsets of required roles in successive calls. Each
   member must reference the same HARNESS_REVIEW_PACKAGE. Stay in the same conversation.
   Batches count as one review round and cannot repeat a reviewer. Record reports
   as each batch finishes, then launch the remaining roles. A failed launch can be
   recovered by regenerating a package; duplicate dispatch is deliberately refused.
   Legacy packages retain their single-invoke restriction and cannot establish
   current final approval. Keep existing read-only reviewer tool permissions.
4. For batched or portable execution, use `record_review.py --pkg <hash> --leaf
   <role> --verdict <TOKEN> --report <json>`. Batched completion uses structured
   reports, never transcript tokens alone. A full native non-batched review retains
   its transcript-compatible path. All required reports must exist before delivery.
   Sequential role checks by one model must be described as self-review.
5. Structured reports may add `checks` entries with a unique `scenario`. For
   `VERIFIED`, provide `artifact: {path, sha256}` pointing to a successful gate JSON
   inside this checkout, bound to the current snapshot/task/engine. For
   `NOT_APPLICABLE`, provide a nonempty reason. `BLOCKED` cannot accompany PASS.
   Referenced artifacts are revalidated at final verdict. The checker proves
   freshness and successful recorded status, not that the artifact semantically
   proves the scenario; reviewers must assess that relationship. Legacy reports
   without checks are explicitly self-reported evidence.
6. Resolve findings, regenerate evidence after input changes, and apply the review
   round cap. Run preflight, affected build tasks and configured device verification.
   Only `final_verdict.py` reporting APPROVED establishes current gate completion.
   Missing device/target access must be disclosed; do not claim unexecuted scenarios.

See `.agents/EVIDENCE.md` for the full report and device contracts, and the Android
competency matrix for selecting scenarios. Lifecycle, release and KMP skills are
loaded only for relevant changes. No Git publishing or permission changes are
implied by this workflow.
