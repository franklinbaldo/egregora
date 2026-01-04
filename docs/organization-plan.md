# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure has a `utils` directory that has been significantly cleaned up. There is some code duplication between the v2 and v3 modules, particularly in the RAG text processing logic.

## Identified Issues

1.  **Duplicated Chunking Logic**: The `simple_chunk_text` function is implemented in both `src/egregora/rag/ingestion.py` (v2) and `src/egregora_v3/infra/rag.py` (v3). This violates the DRY principle and creates maintenance overhead.

## Prioritized Improvements

1.  **Consolidate Chunking Logic**: **[HIGH PRIORITY]** Refactor the duplicated `simple_chunk_text` function into a single, shared module at `src/egregora/text_processing/chunking.py`. Both the v2 and v3 RAG modules will be updated to use this new centralized function. This will improve maintainability and reduce code duplication.

## Abandoned Improvements

*   **Refactor `src/egregora/knowledge/profiles.py`**: **[ATTEMPTED - FAILED]** An attempt was made to refactor the `profiles.py` module by moving the author-syncing logic to a dedicated module in the `mkdocs` adapter. The refactoring failed due to a complex circular dependency that could not be easily resolved. All changes were reverted. This refactoring should be re-evaluated in the future with a more comprehensive understanding of the codebase's dependency graph.

## Completed Improvements

*   **2026-01-05**: Centralized the v2 exception hierarchy by creating a single `EgregoraError` base class in `src/egregora/exceptions.py` and refactoring all custom exceptions to inherit from it. This improves maintainability and enables consistent high-level error handling.
*   **2026-01-04**: Refactored `slugify` from `utils/paths.py` to `utils/text.py`.
*   **2026-01-04**: Moved API key utilities from `utils/env.py` to `llm/api_keys.py`.
*   **2026-01-03**: Moved `GlobalRateLimiter` from `utils/rate_limit.py` to `llm/rate_limit.py`.
*   **2026-01-03**: Removed legacy site scaffolding wrapper from `init/`.
*   **2026-01-02**: Moved domain-specific datetime functions to `output_adapters/mkdocs/markdown_utils.py`.
*   **2026-01-02**: Removed duplicated `run_async_safely` function.
*   **2026-01-01**: Consolidated author management logic into `knowledge/profiles.py`.
*   **2026-01-01**: Moved `UsageTracker` from `utils/metrics.py` to `llm/usage.py`.

## Organizational Strategy

My primary strategy is to inspect the `src/egregora/utils` directory, as it has historically been a collection point for domain-specific logic that should be co-located with its primary users. Each module within `utils` will be evaluated by tracing its usage to determine if it's a true, cross-cutting concern or if it can be moved to a more specific domain. A secondary strategy is to identify and fix cross-cutting organizational issues like code duplication between the v2 and v3 modules.
