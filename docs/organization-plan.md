# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase contains two parallel versions: `egregora` (v2) and `egregora_v3`. While some effort has been made to centralize shared logic, there are still instances where the newer v3 module has a direct and improper dependency on the internals of the v2 module. This creates tight coupling and hinders independent development.

## Identified Issues

1.  **V3 Dependency on V2 Implementation**: The `egregora_v3` RAG module directly imports and uses the `simple_chunk_text` function from `src/egregora/text_processing/chunking.py`. This is an architectural smell, as the new v3 system should not be coupled to the implementation details of the legacy v2 system.

## Prioritized Improvements

1.  **Create Version-Agnostic Shared Module**: **[HIGH PRIORITY]** Decouple the v3 module from the v2 module by moving the shared text processing logic to a version-agnostic location. The `src/egregora/text_processing/` directory will be moved to a new `src/egregora_shared/text_processing/` location, and both v2 and v3 consumers will be updated to import from this new shared path.

## Abandoned Improvements

*   **Refactor `src/egregora/knowledge/profiles.py`**: **[ATTEMPTED - FAILED]** An attempt was made to refactor the `profiles.py` module by moving the author-syncing logic to a dedicated module in the `mkdocs` adapter. The refactoring failed due to a complex circular dependency that could not be easily resolved. All changes were reverted. This refactoring should be re-evaluated in the future with a more comprehensive understanding of the codebase's dependency graph.

## Completed Improvements

*   **2026-01-05**: Moved `media.py` and `taxonomy.py` from the misplaced `src/egregora/orchestration/pipelines/modules` directory to `src/egregora/ops`. This co-locates domain-specific media and taxonomy logic in a more intuitive and discoverable `ops` module, improving the overall codebase structure.
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

My primary strategy is to identify and resolve organizational issues that cross-cut the v2 and v3 modules, such as improper dependencies or duplicated code. A secondary strategy is to continue inspecting the `src/egregora/utils` directory, as it has historically been a collection point for domain-specific logic that should be co-located with its primary users.
