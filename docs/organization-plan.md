# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure has a `utils` directory that has been significantly cleaned up. The v3 `core` module contains some misplaced domain-specific logic.

## Identified Issues

1.  **`src/egregora_v3/core/utils.py`**: The `simple_chunk_text` function, a utility for chunking text for RAG, is located in the core `utils` module. This violates the Single Responsibility Principle, as the core should be domain-agnostic.

## Prioritized Improvements

1.  **Refactor `src/egregora_v3/core/utils.py`**: **[HIGH PRIORITY]** Move the `simple_chunk_text` function to `src/egregora_v3/infra/rag.py`, where it is exclusively used. This will improve modularity by co-locating the function with its related RAG logic.

## Abandoned Improvements

*   **Refactor `src/egregora/knowledge/profiles.py`**: **[ATTEMPTED - FAILED]** An attempt was made to refactor the `profiles.py` module by moving the author-syncing logic to a dedicated module in the `mkdocs` adapter. The refactoring failed due to a complex circular dependency that could not be easily resolved. All changes were reverted. This refactoring should be re-evaluated in the future with a more comprehensive understanding of the codebase's dependency graph.


## Completed Improvements

*   **2026-01-05**: Centralized core exceptions by moving `EgregoraError` and its subclasses from `utils/text.py` to a new `core/exceptions.py` module.
*   **2026-01-04**: Refactored `slugify` from `utils/paths.py` to `utils/text.py`.
*   **2026-01-04**: Moved API key utilities from `utils/env.py` to `llm/api_keys.py`.
*   **2026-01-03**: Moved `GlobalRateLimiter` from `utils/rate_limit.py` to `llm/rate_limit.py`.
*   **2026-01-03**: Removed legacy site scaffolding wrapper from `init/`.
*   **2026-01-02**: Moved domain-specific datetime functions to `output_adapters/mkdocs/markdown_utils.py`.
*   **2026-01-02**: Removed duplicated `run_async_safely` function.
*   **2026-01-01**: Consolidated author management logic into `knowledge/profiles.py`.
*   **2026-01-01**: Moved `UsageTracker` from `utils/metrics.py` to `llm/usage.py`.

## Organizational Strategy

My primary strategy is to identify and refactor modules that violate the Single Responsibility Principle, such as generic `utils` or `constants` files. Each component will be evaluated by tracing its usage to determine if it's a true, cross-cutting concern or if it should be moved to a more specific domain.
