# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The Egregora codebase is a modular Python application with a clear separation between core logic (`src/egregora`), tests (`tests/`), and documentation (`docs/`). The `src/egregora` directory is further subdivided into domain-specific modules such as `agents`, `database`, `knowledge`, `media`, and `llm`. The `utils` directory has been largely dismantled, with some remaining generic utilities in `common`.

## Identified Issues

- **Generic "Common" Logic:** The `src/egregora/common` directory contains generic utilities like `datetime_utils.py` and `text.py`. While these are less problematic than `utils`, they should be monitored to ensure they don't become a dumping ground.
- **Misplaced Domain Logic:** There might still be other files or packages that are not strictly domain-aligned.

## Prioritized Improvements

1.  **Monitor `src/egregora/common`:** Ensure that only truly generic, widely-used utilities remain here.
2.  **Review `src/egregora/data_primitives`:** Ensure that it only contains data structures and not logic.

## Completed Improvements

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
- **Refactored `ops` package:** Eliminated the ambiguous `src/egregora/ops` package.
    - Moved `taxonomy.py` to `src/egregora/knowledge/taxonomy.py`.
    - Created `src/egregora/media` package and moved `media.py` to `src/egregora/media/processing.py`.

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
