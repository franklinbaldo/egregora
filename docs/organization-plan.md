# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The Egregora codebase is a modular Python application with a clear separation between core logic (`src/egregora`), tests (`tests/`), and documentation (`docs/`). The `src/egregora` directory is further subdivided into domain-specific modules such as `agents`, `database`, and `llm`. The legacy `utils` and `common` directories have been successfully eliminated, with their contents moved to domain-specific locations or `data_primitives`.

## Identified Issues

- **Misplaced Domain Logic:** The `src/egregora/utils` directory likely contains code that is specific to other domains within the application. For example, my past journal entries indicate that I've moved `llm`, `author`, `datetime`, and `metrics` related code out of `utils` and into more appropriate, domain-specific modules. It is highly probable that other such instances exist.

## Prioritized Improvements

1.  **Systematically Refactor `src/egregora/utils`:** The highest priority is to continue the work of dismantling the `utils` directory. Each module within it will be analyzed to determine if its contents are truly generic or if they belong to a specific domain. Domain-specific code will be moved to its rightful home, and the corresponding tests will be relocated and consolidated. This will be an ongoing effort, with each session focusing on a single, cohesive refactoring.

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
- **`common` directory elimination:** Moved `src/egregora/common/text.py` and `datetime_utils.py` to `src/egregora/data_primitives/`.
- **`protocols.py` elimination:** Removed redundant `src/egregora/data_primitives/protocols.py` and unified usage under `src/egregora/data_primitives/document.py`.

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
