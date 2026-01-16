# Codebase Organization Plan

Last updated: 2026-01-15

## Current Organizational State

The Egregora codebase is a modular Python application with a clear separation between core logic (`src/egregora`), tests (`tests/`), and documentation (`docs/`). The `src/egregora` directory is further subdivided into domain-specific modules. The `utils` directory has been successfully refactored and eliminated, and a `common` directory now houses genuinely cross-cutting concerns.

However, new areas for improvement have been identified. The `data_primitives` directory, for instance, has shown a tendency to mix concrete data structures with abstract behavioral protocols, violating the Single Responsibility Principle.

## Identified Issues

- **Mixing of Data and Behavior:** The `src/egregora/data_primitives` directory has become a new area of focus. Modules within this directory have been found to contain both concrete dataclasses and abstract protocols, leading to a violation of the Single Responsibility Principle and creating organizational friction.

## Prioritized Improvements

1.  **Systematically Refactor `src/egregora/data_primitives`:** The highest priority is to ensure a clean separation of concerns within the `data_primitives` directory. Each module will be analyzed to ensure that it contains either concrete data structures or abstract protocols, but not both. Any misplaced definitions will be moved to their correct location, and the corresponding tests will be updated.

## Completed Improvements

- **Protocol Consolidation:** Moved the `UrlConvention`, `OutputSink`, and `SiteScaffolder` protocols, along with the `UrlContext` and `DocumentMetadata` dataclasses, from `src/egregora/data_primitives/document.py` to `src/egregora/data_primitives/protocols.py`. This refactoring enforces a clean separation between data primitives and behavioral contracts.
- **`diagnostics.py` module:** Moved from `src/egregora/diagnostics.py` to `src/egregora/cli/diagnostics.py`.
- **`estimate_tokens` function:** Moved from `src/egregora/utils/text.py` to `src/egregora/llm/token_utils.py`.
- **Author management logic:** Moved from `src/egregora/utils/authors.py` to `src/egregora/knowledge/profiles.py`.
- **`UsageTracker` class:** Moved from `src/egregora/utils/metrics.py` to `src/egregora/llm/usage.py`.
- **Async utility:** Removed duplicated `run_async_safely` from `src/egregora/orchestration/pipelines/write.py`.
- **Datetime utilities:** Moved from `src/egregora/utils/datetime_utils.py` to `src/egregora/output_adapters/mkdocs/markdown_utils.py`.
- **Site scaffolding:** Replaced legacy `ensure_mkdocs_project` with `MkDocsSiteScaffolder`.
- **Rate limiter:** Moved from `src/egregora/utils/rate_limit.py` to `src/egregora/llm/rate_limit.py`.
- **`slugify` utility:** Moved from `src/egregora/utils/paths.py` to `src/egregora/utils/text.py`.
- **API key utilities:** Moved from `src/egregora/utils/env.py` to `src/egregora/llm/api_keys.py`.

## Organizational Strategy

My strategy is to follow a systematic, Test-Driven Development (TDD) approach to refactoring. For each organizational improvement, I will:

1.  **Identify:** Locate a piece of misplaced code.
2.  **Test:** Ensure that the code is covered by tests. If not, I will write them.
3.  **Move:** Relocate the code to a more appropriate, domain-specific module.
4.  **Update:** Update all consumer imports to point to the new location.
5.  **Verify:** Run the full test suite to ensure that no regressions have been introduced.
6.  **Clean:** Remove any now-empty files or directories.
7.  **Document:** Update this plan and my journal to reflect the changes.

This iterative process will gradually improve the codebase's organization, making it easier to navigate, understand, and maintain.
