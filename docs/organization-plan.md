# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is a mix of `egregora` (v2) and `egregora_v3` modules. The v2 structure contains a `utils` directory and a `constants.py` file which have historically held misplaced domain-specific code.

## Identified Issues

1.  **`src/egregora/utils/` modules**: The `utils` directory has historically contained misplaced domain logic. A full audit is needed to ensure all remaining modules are true, cross-cutting utilities.

## Prioritized Improvements

*   Continue the systematic evaluation of the `src/egregora/utils` directory.
1.  **`src/egregora/constants.py`**: **[HIGH PRIORITY]** This module acts as a "junk drawer" for various constants and enums. Investigation shows that most enums are either unused (dead code) or belong to a specific domain (e.g., `config`, `rag`). This violates the Single Responsibility Principle and makes the codebase harder to navigate.
2.  **`src/egregora/utils/datetime_utils.py`**: **[EVALUATED - OK]** This module was investigated as a potential candidate for refactoring. However, a `grep` search revealed its functions are used across multiple, disparate domains. It serves as a true, cross-cutting utility and is correctly located. No action is required.

## Prioritized Improvements

1.  **Refactor `src/egregora/constants.py`**: Move domain-specific enums (`RetrievalMode`, `SourceType`, `WindowUnit`) to a new `src/egregora/config/enums.py` file. Delete dead code (`FileFormat`, `IndexType`, `MediaType`) from the module. This will improve modularity and code clarity.

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
