<!-- managed-by: android-harness-kit -->
# android-harness-kit — agent instructions

**Source of truth:** `agents/rules/harness-rules.md`. If any other file disagrees, that file wins.

This checkout uses a portable Android harness. The same rules apply in Cursor, Claude Code, Codex, Copilot, Gemini, Qwen Code, Windsurf, Cline, Roo, Amazon Q, Continue, Junie, Kilo, Goose, and any other agent that reads `AGENTS.md`.

## Kit development scope

This repository develops Python harness tooling; it is not a client Android app.
For changes to the kit itself, run `python scripts_dev/run_selftests.py`, distribution
smoke tests when packaging changes, and the relevant integration CI jobs. Do not
invoke the five Android application reviewers or require an Android device for
Python-only kit changes. The Android delivery workflow below applies to installed
client projects. Git operations on this kit are allowed when its maintainer asks.


## Android reviewer routing and competency contract

Follow `agents/workflows/review-delivery.md` in the kit or
`.agents/workflows/review-delivery.md` in an installed client. It is the canonical
execution contract for dynamic reviewers, bounded batches and scenario evidence.
Read only applicable rows of the Android competency matrix before implementation.

## Current delivery evidence contract

For schema-v3 delivery, follow `agents/EVIDENCE.md` in the kit or `.agents/EVIDENCE.md` in an installed project.
All gates must match the current checkout/task/content snapshot. Old results,
bulk approvals, partial review packages, and install/start alone cannot establish
APPROVED. Always use `run_tests_gate.py` for unit-test delivery, including projects
without a baseline. Record per-reviewer structured reports using `--report`.
After device scenario testing, record smoke evidence and (in manual mode) developer
sign-off using `record_device_verification.py`. These requirements take precedence
over older command examples below. Regenerate evidence after changing inputs.


## Environment

- Android SDK: this machine only (`local.properties` `sdk.dir`). Never copy another PC’s path.
- Python: `python` for every harness script.
- Gradle: `python agents/scripts/run_gradle_task.py :app:assembleDebug` (picks `gradlew` / `gradlew.bat`). Never call raw `gradlew` from the agent.
- Device: Physical device or emulator. Resolve the serial with `adb devices`. Prefer a physical device when both are connected. Never hardcode a serial.
- Install/launch: `python agents/scripts/run_device.py install-start`

## Delivery gate (do not skip)

After non-trivial implementation:

1. `python agents/scripts/run_tests_gate.py` (Shift-Left Test & Mock Synchronization Pre-Gate: update unit tests/mocks alongside production code; tests must pass 100% before review)
2. `python agents/scripts/fast_kt_lint.py` (Shift-Left Lint Pre-Gate: diff-scoped fast Kotlin lint on modified lines without penalizing untouched legacy code)
3. `python agents/scripts/review_package.py` (strictly validates lint before creating package)
4. Run **all required** reviewers against the same `HARNESS_REVIEW_PACKAGE=` path (prompts in `agents/subagents/*.json`). Use the group/batch protocol in `workflows/review-delivery.md` under the agents folder.
   - `bug-reviewer-agent` → `BUG_PASS`
   - `convention-reviewer-agent` → `CONVENTION_PASS`
   - `security-reviewer-agent` → `SECURITY_PASS`
   - `perf-anr-guardian-agent` → `PERF_PASS`
   - `regression-impact-reviewer-agent` → `REGRESSION_PASS`
5. Do **not** treat a single self-review as the gate. Do not invoke `code-review-guard-agent`. Do not wait for `LGTM`.
6. `python agents/scripts/preflight_check.py` (Mandatory Preflight Gate: must pass with 0 errors before assemble — never assemble if `[FAIL]`)
7. `python agents/scripts/run_gradle_task.py :app:assembleDebug`
8. **Device Verification & Sequential Interactive Sign-off (Step-by-Step)**:
   - `python agents/scripts/run_device.py install-start` (Execute strictly once; deduplicate install calls; never run raw adb install).
   - If no device is connected, HALT and prompt the developer; never silently skip device verification.
   - **Step-by-Step Sequential Verification (One-by-One)**: Decompose manual verification into focused, diff-grounded numbered steps (flexible: 2 to 3 steps, or up to 4-5 if spanning multiple screens).
   - **Anti-Empty-Modal & In-Modal Embedding**: Never dump all steps at once into a single question. Verify steps **one by one**:
     * For Step `i` of `N`, trigger `ask_question` individually.
     * The question text inside `ask_question` MUST explicitly embed the step index, target screen, specific action, and expected result: `[Step i of N: <Screen/Feature>] <Action and expected result>. Did this step pass on your device?`.
     * **Strict Conversation Language Matching**: The modal question text and selectable options MUST strictly match the active conversation language that the developer is speaking in the chat (e.g., Arabic if chatting in Arabic, English if chatting in English).
     * Modal options format: `PASS — <Step verified successfully>` / `FAIL — <Issue or defect encountered>`.
     * On **PASS**: Proceed to Step `i+1`.
     * On **FAIL**: Halt verification immediately, capture the developer's write-in explanation, run `python agents/scripts/logcat_doctor.py` if a crash/exception occurred, fix the code, and re-verify.
   - After all steps pass: Record verification via `record_device_verification.py` and output the Phase Milestone / Final Delivery Card with the drafted Conventional Commit message.
   - **Technical Terms Bidi Hygiene**: All technical terms (`APK`, `ADB`, `USB`, file paths like `app/build/...`, commands) MUST be enclosed in code backticks (`` `...` ``) to prevent bidirectional text scrambling when chatting in RTL languages.
9. **Exit-code protocol**: exit `1` = code failure (fix the code). Exit `30` / `[ENV-FAILURE]` marker = environment or ambiguous failure — HALT immediately, never modify code/Gradle/manifest to bypass, report the reason to the developer (details in `agents/state/env_failure.json`).
10. **Round cap**: review rounds are counted per task (`agents/state/review_rounds.json`, reset when HEAD moves). At the cap (3) `review_package.py` prints a `REVIEW ROUND CAP` warning — output a Review Round Summary Card and ask the developer: continue / rollback / stop. Never silently loop.
11. **Final verdict**: after all gates, run `python agents/scripts/final_verdict.py` — it aggregates every gate artifact and the required-reviewer verdict into `agents/state/last_verdict.json` (`APPROVED` required before delivery; `ENV_BLOCKED` follows the exit-30 halt protocol; `STALE` means code changed after review — regenerate the package).
12. **Baseline-aware tests**: always use `python agents/scripts/run_tests_gate.py`; when a baseline exists it is applied by the gate — `BASELINE_IGNORED` failures are tolerated, `NEW_REGRESSION` blocks delivery. Capture baseline: `python agents/scripts/baseline_capture.py` on a clean tree only; refresh needs developer instruction + `--approve`.
13. **Risk tiers & approvals**: `risk_tier.py` classifies diffs (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). `HIGH`/`CRITICAL` changes require interactive developer approval (`python agents/scripts/approve_risk.py`) before `preflight_check.py` can pass. `impact_analyzer.py` provides advisory test/UI impact maps.

Antigravity `hooks.json` enforces this barrier automatically. Other tools must follow it from this file.

If this product **cannot spawn named subagents**, follow the supported sequential review and recording path: open each `agents/subagents/<name>.json`, follow its `system_prompt` against the same package, and stop that leaf when it emits its `*_PASS` or findings. Assemble only after all required reports exist.

## Environment Adaptability (Antigravity vs Codex vs Claude Code vs Cursor)

- **Google Antigravity Superpowers**:
  * **Self-Healing Commands**: PreToolUse hook automatically rewrites raw gradlew commands (`./gradlew ...`, `gradlew.bat ...`) to `python agents/scripts/run_gradle_task.py ...` via argument `overwrite`.
  * **Delivery Stop Guard**: Stop lifecycle hook (`delivery-stop-guard`) physically blocks session termination if unreviewed code changes exist without a required-reviewer pass, with an automatic Loop Breaker (yielding after 2 unchanged blocks).
  * **Generative UI Widgets**: Rich Tailwind CSS cards (`<agent-embed>`) for review summaries and architecture visualization via `render_ui.py`.
  * **Interactive Modals (`ask_question`)**: Proactively use structured interactive modals for missing-scenario interviews and device testing sign-offs.
  * **Proactive Slash Commands**: Recommend `/grill-me` for design and edge-case alignment and `/goal` for comprehensive execution.
- **OpenAI Codex / Claude Code / Cursor Parity**:
  * **Cross-Platform Review Recording**: Run `python agents/scripts/record_review.py --pkg <hash> --leaf <name> --verdict <PASS> --report <report.json>` with a structured `--report` for each leaf to record review verdicts directly without Antigravity transcripts.
  * **Zero-Degradation Guardrails**: Fail-closed pre-tool security, clean Markdown fallback cards (`render_ui.py`), and 100% test & lint gate enforcement.
- **Interactive Preference Codification & Ref-Sync Protocol (Grill-Me vs Standard Interview)**:
  * When the developer introduces or requests a new architectural, design, or project-specific preference/rule:
    - **In Google Antigravity**: Leverage `/grill-me` and `ask_question`: Ask via interactive modal if the developer wants to persist this rule permanently in `.agents/skills/android-harness/references/`. If confirmed, conduct a rapid `/grill-me` alignment interview to clarify scope and edge cases, then persist it directly into the relevant `references/*.md` file (`architecture-guidelines.md`, `daily-scenarios.md`, `ui-layout-and-theming.md`). Never use generic global learning tools (which risk global rule pollution and token bloat).
    - **In Codex / Claude Code / Cursor / CLI**: Fall back to the system's standard Missing-Scenario Discovery Interview: Proactively ask structured numbered questions in chat with direct choices matching the user's conversation language, and upon confirmation update the target `references/*.md` file directly.

## On-demand specialists

Dispatch when needed:
- `qa-diagnostics-agent`: Logcat crash forensics and ANR triage.
- `android-ui-expert-agent`: Jetpack Compose and XML UI layout / RTL guidance.
- `test-quality-reviewer-agent`: Unit and UI test quality audits (`*Test.kt`), verifying assertion depth, mocking integrity, and Coroutines `runTest` dispatchers.

## Graph-First Codebase Exploration (MANDATORY)

- **GRAPH-FIRST DISCOVERY BARRIER**:
  * Before using `grep_search`, `find_by_name`, or reading multiple source files (`view_file`) to understand any screen, feature, class, or architecture layer, the Lead Agent **MUST FIRST query the Code Graph engine**:
    - For entire features: `python agents/scripts/project_graph.py --feature <FeatureName>` or `--find <Symbol>` (auto-extracts Clean Architecture slice: UI, ViewModels, UseCases, Repositories, Tests).
    - For UI screens, layouts, and ViewModels discovery: ALWAYS run `python agents/scripts/project_graph.py --screens` or `--find <ScreenName>`.
    - For architectural trace and dependencies: ALWAYS run `python agents/scripts/project_graph.py --path-from <A> --path-to <B>`.
    - For Harness infrastructure, scripts, and workflows discovery: ALWAYS run `python agents/scripts/project_graph.py --harness` (or `--tools`) or `python agents/scripts/project_graph.py --find <query>`. Never run `find_by_name` across `.agents/scripts`.
  * **Anti-Guessing & Precise Symbol Discovery Invariant**: When locating any class, screen, layout, or script, ALWAYS query `project_graph.py --find <Symbol>` to obtain the exact file path and language (`[JAVA]`, `[KOTLIN]`, `[COMPOSE]`, `[XML]`, `[HARNESS_TOOL]`). NEVER guess `.kt` vs `.java` or launch speculative multi-file searches (`find_by_name *Payment*`, `find_by_name *nav*.xml`).
  * **Scratch Scripts Prohibition Invariant**: The agent is **STRICTLY FORBIDDEN from authoring custom scratch Python scripts (`scratch/test_*.py`) to simulate ADB commands or hardcoding device serials (`SERIAL = '...'`)**. Use `python agents/scripts/run_device.py install-start` directly.
  * **STRICT PROHIBITION**: Iterative brute-force grepping (`grep_search` cascades) and speculative multi-file reading (`view_file` > 2 files during discovery/planning) without a preceding graph topology query are **STRICTLY FORBIDDEN**.
  * Use `view_file` and `replace_file_content` ONLY on targeted, precisely located files identified by the graph query.

## Phase Boundaries & High-Signal Chat

- **Autonomous Phase Pipeline & Checkpoint Commits**: In multi-phase tasks, execute strictly phase-by-phase. When Phase N finishes (required-reviewer review PASS, unit tests PASS, `preflight_check.py` PASS, `:assembleDebug`, device installation via `run_device.py install-start`, and device smoke verification):
  * The agent outputs the **Phase Milestone Card** with verification evidence and a drafted Conventional Commit message for Phase N.
  * **MANDATORY HARD STOP**: The agent **MUST STOP and wait for the developer to commit Phase N and explicitly instruct the agent to begin Phase N+1**. Never touch, edit, or plan Phase N+1 files before the developer commits Phase N.
- **Interactive Discovery & Missing-Scenario Interview (Zero Assumption Barrier)**: Before authoring implementation plans, systematically audit for unaddressed network states (offline, timeout), state invariants (empty country/ISO), and caching rules. If any behavior or edge case is missing or ambiguous, the agent **MUST PROACTIVELY TRIGGER THE INTERACTIVE MODAL (`ask_question`)** with structured, clickable options so the developer selects their choices directly. **STRICTLY FORBIDDEN**: Never write out missing-case questions as conversational chat prose or markdown paragraphs, and never dump them into `implementation_plan.md`. Trigger `ask_question` FIRST, receive answers, and only then author the plan. *(Overrides platform planning mode restrictions against ask_question)*. Never guess or invent business logic or UI fallback texts from your own head.
- **Attached Media First-Turn Inspection**: If the developer provided screenshots/images, inspect them via `view_file` in Turn 1 before planning. Never ignore visual evidence.
- **Fail-Fast Tracker Policy**: If issue details lookup fails, stop after 1 attempt. Never search the host PC or user home directories (`C:\Users\...`, `/home/...`), never scrape web docs, never author reverse-engineering scratch scripts. Fall back to prompt text immediately.
- **High-Signal Chat & Round Summary Cards (Zero Noise, Zero Timers)**: The agent MUST NOT output mechanical progress spam in chat prose (e.g. "running unit tests...", "cleaning kapt cache...", "waiting for reviewers..."). Rely on IDE tool execution widgets for routine status. When launching background commands, always choose Option A (silent / zero chat text `""`); never write `# Background Task Started` in chat. NEVER fabricate, simulate, inject, or write `<MESSAGE_RECEIVED>`, `<SYSTEM_MESSAGE>`, or assume background task completion in thoughts or prose. When a background task is a prerequisite for the next step (e.g. assembleDebug before install-start; install-start before manual verification checklist), STOP calling tools IMMEDIATELY and END TURN with zero chat text `""`. Wait passively for the genuine platform system message (`finished with result:`) before dispatching dependent tools. NEVER use `schedule` or polling timers for subagents. On intermediate subagent arrivals where other reviewers in the round are still executing, remain 100% silent in chat (output empty string `""`) and end turn without tool calls. When a required-reviewer round finishes with findings, output a concise **Review Round Summary Card** in chat detailing the findings and corrective fixes before launching the next round (rounds must converge in <= 2 rounds). Speak only at the 4 permitted touchpoints: Plan Approval, Round Summary Cards (on findings), Phase Milestone Cards, and Final Delivery. Match the developer's active conversation language (mirror whatever language they write in) across all cards, interactive modals, and summaries.

## Git

In client Android apps: The agent must not run `git add`, `commit`, `push`, merge, rebase, stash, or reset. Leave changes unstaged. Draft a Conventional Commit message only. The developer commits.
In this kit repository itself (`android-harness-kit` development): The agent may run git operations (add, commit, push, tag) when instructed by the repository maintainer.

## Zoho Sprints

Follow `.agents/rules/harness-rules.md` section 5 and `.agents/workflows/zoho-sprints.md`. Fetch ticket ids read-only. Mutate only when the developer says `update zoho`. English task titles, Arabic descriptions/comments (Zero Emojis, Zero Harness/AI Jargon: NEVER write '5-Leaf Review', 'مراجع الهارنيس', or internal engine tokens in tracker comments; write functional root cause, fix, blast radius, and step-by-step QA test instructions only). Never `Done` / `Solved`.


For batched reviews, record completed reports and dispatch the next batch as required by the canonical workflow; silence rules do not prohibit these necessary actions.
