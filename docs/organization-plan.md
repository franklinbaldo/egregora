# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure has a `utils` directory that has been significantly cleaned up. The v3 `core` module contains some misplaced domain-specific logic.

## Identified Issues

*No high-priority issues have been identified yet. The next step is to continue discovery.*

## Prioritized Improvements

*No high-priority improvements have been identified yet. The next step is to continue discovery.*

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

My primary strategy is to inspect the `src/egregora/utils` directory, as it has historically been a collection point for domain-specific logic that should be co-located with its primary users. Each module within `utils` will be evaluated by tracing its usage to determine if it's a true, cross-cutting concern or if it can be moved to a more specific domain. A secondary strategy is to identify and fix cross-cutting organizational issues like the inconsistent exception hierarchy.
