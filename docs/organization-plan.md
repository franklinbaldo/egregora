# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase has undergone significant refactoring to improve modularity. Much of the logic previously located in the generic `src/egregora/utils` directory has been moved to appropriate domain-specific modules.

However, a new organizational issue has emerged: the `src/egregora/utils` directory now contains several **compatibility shims**. These modules exist only to re-export code from other locations, creating unnecessary indirection and clutter. This makes the codebase harder to navigate, as it's not always clear where the source of truth for a given function or class is located.

## Identified Issues

1.  **Stale Organization Plan**: This plan was critically out of date, listing several issues that had already been resolved. This has been updated.
2.  **Compatibility Shims in `utils`**: The `src/egregora/utils` directory contains multiple files that serve only to re-export code from other, more domain-specific locations. This creates indirection and makes the codebase harder to navigate.
    -   `src/egregora/utils/authors.py`: Re-exports `AuthorsFileLoadError` from `egregora.knowledge.exceptions`.
    -   `src/egregora/utils/cache.py`: Re-exports multiple caching components from `egregora.orchestration.cache`.

## Prioritized Improvements

1.  **Remove `authors.py` Shim (High Impact, Low Risk)**: This shim is a single, straightforward re-export. Removing it and updating its consumers is a small, safe change that will immediately improve clarity. This is the focus of the current session.
2.  **Remove `cache.py` Shim (High Impact, Low Risk)**: Similar to the `authors.py` shim, this module creates unnecessary indirection. Its removal will be a simple, high-impact improvement.

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
- **Security code (`safe_path_join`) consolidated in `security/fs.py`**

## Organizational Strategy

My strategy is to eliminate compatibility shims and other forms of indirection from the codebase. I will systematically identify and remove these shims, updating all consumers to import directly from the canonical source. This will make the code easier to navigate and understand. I will continue to follow a test-driven approach for each refactoring, ensuring that all changes are safe and behavior-preserving.
