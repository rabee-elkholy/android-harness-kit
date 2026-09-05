---
description: Implement or refactor, atomic per-phase review, test gate, assemble, device validation, and sign-off.
---

# Deliver an Android change

Follow `.agents/rules/harness-rules.md` exactly. Do not commit. Do not use worktrees. Do not invoke `code-review-guard-agent`.

## Steps

1. **Inspect & Plan**: For non-trivial work, consult `brainstorming/SKILL.md` and write `implementation_plan.md` artifact (`RequestFeedback: true`). Present Milestone Delivery Strategy for multi-phase tasks and proactively ask in chat about Zoho Sprints story/tasks creation. Wait for developer approval via native Proceed button.
2. **Atomic Phase Execution (Repeat per Phase)**:
   - **TDD & Code**: Follow `test-driven-development/SKILL.md` (Red -> Prove Failure -> Green -> Refactor).
   - **Stage 0 Shift-Left Test & Lint Pre-Gate**: Run `python .agents/scripts/run_gradle_task.py :app:testDebugUnitTest` AND `python .agents/scripts/fast_kt_lint.py` to catch compiler mismatches, `!!`, `TODO`s, and missing `@Preview`s before requesting reviews.
   - **Stage 0.5 Test Specialist Gate**: If test files (`*Test.kt`) are modified/added, dispatch `test-quality-reviewer-agent` until `TEST_PASS`.
   - **Stage 1 Review Gate**: Follow the required reviewers and batch protocol in review-delivery.md. Zero timers/sleep. Silent wait on intermediate arrivals. When a round finishes with findings, output a **Review Round Summary Card** in chat, fix at root cause, verify with `fast_kt_lint.py`, and re-dispatch until all required reviewers emit `*_PASS`.
   - **Stage 2 Mandatory Preflight Gate & Assemble**: Run `python .agents/scripts/preflight_check.py` (MUST be `[SUCCESS]`; never proceed if `[FAIL]`) and `python .agents/scripts/run_gradle_task.py :app:assembleDebug`.
   - **Stage 3 Device Verification & Checkpoint Commit**:
     * Run `python .agents/scripts/run_device.py install-start` strictly once (deduplicate install calls; never run raw adb install). If no device is connected, HALT and prompt developer via `ask_question`; never silently skip.
     * Decompose manual verification into focused, diff-grounded numbered steps (flexible: 2 to 3 steps, or up to 4-5 if spanning multiple screens).
     * **Sequential Verification (One-by-One)**: Verify steps individually via `ask_question`. Embed the step index, target screen, specific action, and expected result directly into the question text: `[Step i of N: <Screen/Feature>] <Action and expected result>. Did this step pass on your device?`.
     * **Strict Conversation Language Matching**: The modal question text and selectable options MUST strictly match the active conversation language that the developer is speaking in the chat. Format: `PASS — <Step verified successfully>` / `FAIL — <Issue or defect encountered>`.
     * On **PASS**: Proceed to the next step until all steps pass.
     * On **FAIL**: Halt verification immediately, capture developer feedback, run `python .agents/scripts/logcat_doctor.py` if an error/crash occurred, fix the code, and re-verify.
     * After all steps pass: Record verification via `record_device_verification.py`, output the Phase Milestone Card with the drafted Conventional Commit message for Phase N.
     * **MANDATORY HARD STOP**: Stop immediately and wait for the developer to commit Phase N and explicitly instruct to begin Phase N+1. Never touch Phase N+1 files before developer commit.
     * **Technical Terms Bidi Hygiene**: All technical terms (`APK`, `ADB`, `USB`, file paths like `app/build/...`, commands) MUST be enclosed in code backticks (`` `...` ``) to prevent bidirectional text scrambling when chatting in RTL languages.
3. **Task Completion**: Output walkthrough summary and final task summary in the active conversation language after all phases are verified and committed.
