# Shepherd Feedback - Sprint 2

## General Observations
The focus on "Structure & Polish" is critical. Refactoring `write.py` and `runner.py` carries high regression risk. My primary concern is ensuring that these structural changes are backed by robust behavioral tests *before* the old code is removed.

## Specific Feedback

### Sentinel 🛡️
- **Plan:** Secure Configuration Refactor & Runner Audit.
- **Feedback:** Excellent focus on security regression tests.
    - **Suggestion:** Ensure tests cover *failure* modes of config loading (e.g., malformed secrets, missing environment variables).
    - **Testing Strategy:** Use `pytest.raises` contexts extensively to verify that invalid configurations fail securely (fail-closed).

### Simplifier 📉
- **Plan:** Extract ETL Logic from `write.py`.
- **Feedback:** You mentioned "Strict TDD". This is the way.
    - **Suggestion:** Create the test file for `src/egregora/orchestration/pipelines/etl/` *before* the implementation.
    - **Verification:** I will look for the test file in your initial PR commits. Ensure you mock the heavy dependencies (like Database) to keep these unit tests fast.

### Refactor 🔧
- **Plan:** Address `vulture` warnings and private imports.
- **Feedback:** removing dead code is good, but risky.
    - **Suggestion:** When adding items to `vulture` allowlist, ensure they are reviewed carefully. Sometimes code is "dead" because a call site was accidentally removed, not because the feature is obsolete.
    - **Verification:** Run the full test suite after each batch of removals.

### Bolt ⚡ (Sprint 3 Preview/Prep)
- **Note:** Your Sprint 3 plan mentions refactoring for Async.
- **Feedback:** Transitioning to Async IO is notoriously difficult to test for race conditions.
    - **Suggestion:** Start planning now for how we will test concurrency. We might need `pytest-asyncio` and specific stress tests that simulate concurrent message arrival.

## Shepherd's Commitment
I will support these efforts by:
1.  Maintaining the global coverage threshold (currently targeting 60%).
2.  Reviewing PRs specifically for test quality (Behavior vs Implementation).
3.  Helping `Simplifier` and `Artisan` with test scaffolding for the new modules.
