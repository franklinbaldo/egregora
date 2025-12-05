# Test Coverage Improvement Report

## 1. Executive Summary

This report analyzes the current state of test coverage in the `egregora` project and outlines a strategic plan to improve it. The current test suite leans heavily on End-to-End (E2E) tests, which are excellent for verifying system integration but can be slow and brittle for testing edge cases. There is a significant gap in Unit Test coverage for core architectural components like Orchestration, Database Internals, and Transformations.

## 2. Current State Analysis

### 2.1 Strengths
*   **Strong E2E Coverage:** The `tests/e2e/` directory contains tests for the CLI, critical pipelines, and adapters, ensuring the "happy path" works.
*   **Golden Fixtures:** The use of golden fixtures and mocked LLM responses (via `vcr` or custom mocks) makes E2E tests deterministic.
*   **Modern Tooling:** The project uses `uv`, `pytest`, and `ruff`, providing a solid foundation for testing.

### 2.2 Gaps & Weaknesses
*   **Missing Unit Tests for Core Logic:**
    *   **Orchestration:** `src/egregora/orchestration` (PipelineFactory, Workers, Persistence) has no dedicated unit tests. This is risky as it controls the application flow.
    *   **Database:** While `DuckDBStorageManager` is tested implicitly via E2E, specific SQL generation logic in `src/egregora/database` (especially dynamic SQL or templates) lacks isolated verification.
    *   **Transformations:** Windowing strategies in `src/egregora/transformations` are not unit tested, making it hard to verify boundary conditions.
    *   **Ops:** Media operations in `src/egregora/ops` are critical for data integrity but lack focused tests.
*   **No Coverage Reporting:** `pytest-cov` is not configured, making it impossible to quantitatively measure improvement.
*   **Fragile External Dependencies:** Tests relying on external tools (like `mkdocs` build process in E2E) can be flaky if not isolated properly.

## 3. High-Level Strategy

We will adopt the **Test Pyramid** approach:
1.  **Base (Unit Tests):** Expand the base significantly to cover individual components in isolation. This allows for fast feedback loops.
2.  **Middle (Integration Tests):** Maintain current integration tests but refactor them to be more focused (e.g., testing `Ibis` -> `DuckDB` interactions specifically).
3.  **Tip (E2E Tests):** Keep existing E2E tests as a sanity check for the full workflow.

## 4. Specific Recommendations

### 4.1 Immediate Actions (Low Effort, High Value)
1.  **Install & Configure `pytest-cov`:**
    *   Add `pytest-cov` to dev dependencies.
    *   Update `pyproject.toml` to fail if coverage drops below a threshold (e.g., 50% initially).
    *   Run `uv run pytest --cov=src/egregora` to establish a baseline.

2.  **Unit Tests for Orchestration:**
    *   Create `tests/unit/orchestration/test_workers.py`: specific tests for `ProfileWorker`, `BannerWorker` verifying error handling and dependency injection.
    *   Create `tests/unit/orchestration/test_factory.py`: verify `PipelineFactory` correctly assembles pipelines with different configs.

### 4.2 Medium Term Actions
3.  **Unit Tests for Database Logic:**
    *   Create `tests/unit/database/test_sql_manager.py`: Test `render()` method with various template contexts to ensure SQL is generated correctly without running it against a DB.
    *   Test schema definitions in `src/egregora/database/ir_schema.py` to ensure they match expected Ibis types.

4.  **Property-Based Testing for Parser:**
    *   Use `hypothesis` to generate random WhatsApp message formats and ensure the parser never crashes (even if it rejects the input).

### 4.3 Long Term / Infrastructure
5.  **Snapshot Testing for Output Adapters:**
    *   Use `syrupy` or `pytest-snapshot` to snapshot the generated HTML/Markdown content from `MkDocsAdapter` to catch regression in rendering logic without manually inspecting files.

6.  **CLI Smoke Test:**
    *   Add a fast "smoke test" that runs `egregora init` and `egregora build` on a minimal dataset to ensure the CLI entry points are functional.

## 5. Action Plan

| Step | Task | Target Component | Estimated Effort |
| :--- | :--- | :--- | :--- |
| 1 | Add `pytest-cov` and run baseline | Infrastructure | Small |
| 2 | Create `tests/unit/orchestration/` | `src/egregora/orchestration` | Medium |
| 3 | Create `tests/unit/database/` | `src/egregora/database` | Medium |
| 4 | Create `tests/unit/transformations/` | `src/egregora/transformations` | Small |
| 5 | Refactor E2E to use new Unit tests | All | Large |

## 6. Conclusion
By shifting focus to Unit Tests for critical "unseen" components like Orchestration and Database internals, we can significantly increase confidence in the codebase. Adding coverage reporting will provide the necessary visibility to track this progress.
