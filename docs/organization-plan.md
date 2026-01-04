# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. This has led to some duplication of core logic, such as utility functions, between the two versions. The v2 structure has a `utils` directory that has been significantly cleaned up, but opportunities for consolidation remain.

## Identified Issues

*No high-priority issues have been identified yet. The next step is to continue discovery.*

## Prioritized Improvements

*No high-priority improvements have been identified yet. The next step is to continue discovery.*

## Abandoned Improvements

*   **Refactor `src/egregora/knowledge/profiles.py`**: **[ATTEMPTED - FAILED]** An attempt was made to refactor the `profiles.py` module by moving the author-syncing logic to a dedicated module in the `mkdocs` adapter. The refactoring failed due to a complex circular dependency that could not be easily resolved. All changes were reverted. This refactoring should be re-evaluated in the future with a more comprehensive understanding of the codebase's dependency graph.

## Completed Improvements

*   **2026-01-05**: Consolidated duplicated RAG chunking logic. The V2 `_simple_chunk_text` function was removed and replaced with a wrapper around the canonical V3 `simple_chunk_text` function. This change eliminates code duplication while preserving the specific behavior of the V2 implementation. All related tests were consolidated into a single file.
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

My primary strategy is to continue inspecting the `src/egregora/utils` directory for misplaced domain-specific logic. A new secondary strategy is to actively look for and consolidate duplicated logic between the v2 (`egregora`) and v3 (`egregora_v3`) codebases, using the v3 implementation as the canonical source where possible. This will reduce maintenance overhead and improve consistency.
