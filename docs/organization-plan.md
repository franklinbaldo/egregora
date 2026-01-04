# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure contains a `utils` directory which often holds misplaced domain-specific code. Previous refactoring has addressed some of these issues, but more may exist. A new `core` package has been created to house shared, foundational code.

## Identified Issues

1.  **`src/egregora/utils/datetime_utils.py`**: **[EVALUATED - OK]** This module was investigated as a potential candidate for refactoring. However, a `grep` search revealed its functions (`ensure_datetime`, `parse_datetime_flexible`, etc.) and exceptions are used across multiple, disparate domains (agents, database, adapters, other utils). It serves as a true, cross-cutting utility and is correctly located. No action is required.

## Prioritized Improvements

*No high-priority improvements have been identified yet. The next step is to continue discovery.*

## Completed Improvements

*   **2026-01-05**: Created `src/egregora/core` package and moved `EgregoraError` from `utils/text.py` to a new `core/exceptions.py` module to centralize base exceptions.
*   **2026-01-04**: Refactored `slugify` from `utils/paths.py` to `utils/text.py`.
*   **2026-01-04**: Moved API key utilities from `utils/env.py` to `llm/api_keys.py`.
*   **2026-01-03**: Moved `GlobalRateLimiter` from `utils/rate_limit.py` to `llm/rate_limit.py`.
*   **2026-01-03**: Removed legacy site scaffolding wrapper from `init/`.
*   **2026-01-02**: Moved domain-specific datetime functions to `output_adapters/mkdocs/markdown_utils.py`.
*   **2026-01-02**: Removed duplicated `run_async_safely` function.
*   **2026-01-01**: Consolidated author management logic into `knowledge/profiles.py`.
*   **2026-01-01**: Moved `UsageTracker` from `utils/metrics.py` to `llm/usage.py`.

## Organizational Strategy

My primary strategy is to inspect the `src/egregora/utils` directory, as it has historically been a collection point for domain-specific logic that should be co-located with its primary users. Each module within `utils` will be evaluated by tracing its usage to determine if it's a true, cross-cutting concern or if it can be moved to a more specific domain. With the creation of `src/egregora/core`, another strategy is to identify any other foundational code that could be moved there.
