---
name: android-state-recovery
description: Verify lifecycle and state restoration when Android changes affect navigation, saved state, collectors or background/foreground transitions; not a blanket gate for unrelated changes.
---

# State recovery verification

Establish the screen entry path, state owner and expected restoration behavior from
the project. Ask about missing product behavior only when it changes the result.

1. Inventory transient UI state, saved state and durable data. Trace their actual
   owners across the screen, ViewModel, repository and persistence boundaries.
2. Choose relevant scenarios: recreation, background/foreground, system process
   termination and relaunch, deep-link entry, back navigation and cancelled work.
   Treat recreation and process death as separate experiments; one does not prove
   the other. Do not represent force-stop as equivalent to normal OS restoration.
3. Use the project's existing test infrastructure for state transitions and
   cancellation. Device scenarios require an actual connected target and observed
   outcomes; preserve the user's device preference. Do not invent serials or logs.
4. For a process-restoration test, record initial state, how the app was backgrounded,
   how process termination was induced, confirmation that the process changed, the
   return route, and restored versus intentionally reset state. Use a disposable
   test account/data where needed. Do not erase user data to manufacture a pass.
5. Inspect duplicate navigation/events, restarted collectors and lost in-flight
   results against the contract. Propose only the smallest change supported by evidence.

Report scenario, target/API, initial state, steps, expected/actual result and evidence
path. Missing device access is BLOCKED for that scenario; static review remains
separately identified. Link successful current gate artifacts through report checks
when available. A generic build artifact does not prove a restoration scenario.

Use the canonical review-delivery workflow for recording and delivery; do not add
another reviewer roster or require unrelated lifecycle scenarios.
