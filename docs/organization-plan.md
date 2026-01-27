# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The Egregora codebase is a modular Python application with a clear separation between core logic (`src/egregora`), tests (`tests/`), and documentation (`docs/`). The `src/egregora` directory is further subdivided into domain-specific modules such as `agents`, `database`, and `llm`. The legacy `utils` and `common` directories have been successfully eliminated, with their contents moved to domain-specific locations or `data_primitives`.

## Identified Issues

- **Leaky Abstractions in Configuration:** While `src/egregora/config/settings.py` serves as the central configuration source, it sometimes accumulates helper logic (like API key fetching) that belongs in domain-specific modules. This should be monitored to keep the config module focused on schema definition and loading.

## Prioritized Improvements

1.  **Monitor `src/egregora/constants.py`:** Ensure constants are grouped logically and consider moving them to domain modules if they are used exclusively within that domain (e.g., `WindowUnit` to `transformations`).
2.  **Verify Module Boundaries:** Continue to audit imports to ensure clean separation of concerns, especially around `data_primitives` and `config`.

## Completed Improvements

- **API Key Logic Consolidation:** Moved all API key fetching logic (Google, OpenRouter) from `src/egregora/config/settings.py` to `src/egregora/llm/api_keys.py`, eliminating duplication and ensuring consistent behavior.
- **`diagnostics.py` module:** Moved from `src/egregora/diagnostics.py` to `src/egregora/cli/diagnostics.py`.
- **`estimate_tokens` function:** Moved from `src/egregora/utils/text.py` to `src/egregora/llm/token_utils.py`.
- **Author management logic:** Moved from `src/egregora/utils/authors.py` to `src/egregora/knowledge/profiles.py`.
- **`UsageTracker` class:** Moved from `src/egregora/utils/metrics.py` to `src/egregora/llm/usage.py`.
- **Async utility:** Removed duplicated `run_async_safely` from `src/egregora/orchestration/pipelines/write.py`.
- **Datetime utilities:** Moved from `src/egregora/utils/datetime_utils.py` to `src/egregora/output_sinks/mkdocs/markdown_utils.py`.
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
