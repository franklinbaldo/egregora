# Issue #019: Consolidate Test Suite and Remove `run_all_tests.py`

- **Status**: Proposed
- **Type**: Cleanup / Developer Experience
- **Priority**: Low
- **Effort**: Low

## Problem

A custom `run_all_tests.py` script duplicates functionality that `pytest` already provides and adds an extra layer for contributors to learn. Some test modules (e.g., `test_enrichment_simple.py`) overlap with more complete suites, suggesting that the test organization could be simplified.

## Proposal

1. **Standardize on pytest.** Ensure every test can be invoked via `uv run pytest` without relying on helper scripts.
2. **Merge redundant tests.** Fold the "simple" test modules into their comprehensive counterparts to reduce duplication.
3. **Remove the script.** Delete `run_all_tests.py` once the suite runs cleanly with standard tooling.
4. **Update documentation.** Reflect the change in `TESTING_PLAN.md`, contributor docs, and any onboarding materials.

## Expected Benefits

- Aligns the project with common Python testing practices.
- Reduces maintenance overhead for custom tooling.
- Makes it easier for new contributors to run the suite.

## Dependencies

- Confirmation that CI and local developer workflows already use `pytest`.
- Coordination with any tooling that invokes `run_all_tests.py` directly (e.g., IDE configurations).
