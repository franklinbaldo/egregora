# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure contains a `utils` directory which often holds misplaced domain-specific code. Previous refactoring has addressed some of these issues, but more may exist.

## Identified Issues

1.  **`src/egregora/utils/` modules**: The `utils` directory has historically contained misplaced domain logic. A full audit is needed to ensure all remaining modules are true, cross-cutting utilities.

## Prioritized Improvements

*   Continue the systematic evaluation of the `src/egregora/utils` directory.

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

My primary strategy is to inspect the `src/egregora/utils` directory, as it has historically been a collection point for domain-specific logic that should be co-located with its primary users. Each module within `utils` will be evaluated by tracing its usage to determine if it's a true, cross-cutting concern or if it can be moved to a more specific domain.
