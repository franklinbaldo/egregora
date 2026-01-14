# Codebase Organization Plan

Last updated: 2026-01-06

## Current Organizational State

The codebase has undergone significant refactoring to improve modularity. The generic `src/egregora/utils` directory has been largely cleaned up, with most domain-specific logic moved to its proper home. However, a few compatibility shims remain, adding unnecessary indirection when navigating the codebase.

The testing structure largely mirrors the source structure, which is good.

## Identified Issues

1.  **Vague `database/utils.py`**: The `src/egregora/database/utils.py` module may contain generic SQL utilities, but it could also hide domain-specific query logic that should be part of a specific repository or data access layer.
2.  **Compatibility Shims in `utils`**: The `src/egregora/utils` directory contains files that re-export code from other, more domain-specific locations.
    -   `src/egregora/utils/authors.py`: Re-exports `AuthorsFileLoadError` from `egregora.knowledge.exceptions`.
    -   `src/egregora/utils/cache.py`: Re-exports caching components from `egregora.orchestration.cache`.

## Prioritized Improvements

1.  **Remove `authors.py` Shim (High Impact, Low Risk)**: This shim is a straightforward re-export. Removing it and updating its consumers will immediately improve clarity.
2.  **Remove `cache.py` Shim (High Impact, Low Risk)**: Similar to the `authors.py` shim, this module creates unnecessary indirection.
3.  **`database/utils.py` Refactoring (Medium Impact, Medium Risk)**: Improve the data access layer with careful analysis to avoid breaking database interactions.

## Completed Improvements

- **`estimate_tokens` moved to `llm/token_utils.py`**
- **Author management moved to `knowledge/profiles.py`**
- **`UsageTracker` moved to `llm/usage.py`**
- **Async utility de-duplicated**
- **Datetime utilities moved to `output_adapters/mkdocs/markdown_utils.py`**
- **Site scaffolding refactored**
- **Rate limiter moved to `llm/rate_limit.py`**
- **`slugify` moved to `utils/text.py`**
- **API key utilities moved to `llm/api_keys.py`**
- **Removed dead code from `database/utils.py`**
- **Removed dead compatibility shims from `utils` (`cache.py`, `authors.py`)**
- **Removed dead compatibility shims from `utils` (`exceptions.py`)**
- **Security code (`safe_path_join`) consolidated in `security/fs.py`**

## Organizational Strategy

My strategy is to systematically dismantle the `src/egregora/utils` directory by moving its modules to their correct, domain-specific locations and eliminating compatibility shims. I will follow a test-driven approach for each move, ensuring that a safety net of tests exists before any code is relocated. Each refactoring will be a single, cohesive change delivered in its own pull request. I will prioritize changes that offer the most significant improvement in clarity for the lowest risk and effort.
