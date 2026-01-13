# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is generally well-structured, with a clear separation of concerns between domains like `llm`, `knowledge`, `orchestration`, and `output_adapters`. However, a significant amount of domain-specific logic still resides in the generic `src/egregora/utils` directory. This directory acts as a "junk drawer" for modules that haven't been assigned a proper home, making the code harder to navigate and understand.

The testing structure largely mirrors the source structure, which is good. However, tests for misplaced modules are also misplaced, perpetuating the organizational issues.

## Identified Issues

1.  **Vague `database/utils.py`**: The `src/egregora/database/utils.py` module may contain generic SQL utilities, but it could also hide domain-specific query logic that should be part of a specific repository or data access layer.

## Prioritized Improvements

1.  **`database/utils.py` Refactoring (Medium Impact, Medium Risk)**: This could improve the data access layer, but requires careful analysis to avoid breaking database interactions.

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
- **Removed unused `utils/cache.py` shim**

## Organizational Strategy

My strategy is to systematically dismantle the `src/egregora/utils` directory by moving its modules to their correct, domain-specific locations. I will follow a test-driven approach for each move, ensuring that a safety net of tests exists before any code is relocated. Each refactoring will be a single, cohesive change delivered in its own pull request. I will prioritize changes that offer the most significant improvement in clarity for the lowest risk and effort.
