# Codebase Organization Plan

Last updated: 2026-01-05

## Current Organizational State

The codebase is generally well-structured, with a clear separation of concerns between domains like `llm`, `knowledge`, `orchestration`, and `output_adapters`. However, a significant amount of domain-specific logic still resides in the generic `src/egregora/utils` directory. This directory acts as a "junk drawer" for modules that haven't been assigned a proper home, making the code harder to navigate and understand.

The testing structure largely mirrors the source structure, which is good. However, tests for misplaced modules are also misplaced, perpetuating the organizational issues.

## Identified Issues

1.  **Misplaced Filesystem Utilities**: The `src/egregora/utils/fs.py` module contains filesystem-related helper functions. These are likely used by output adapters or other components that interact with the filesystem. They should be moved closer to their primary consumers to improve cohesion.
2.  **Misplaced Caching Logic**: The `src/egregora/utils/cache.py` module contains caching utilities. Caching strategies are often tied to specific domains (e.g., caching for LLM calls vs. caching for filesystem access). This module should be broken up and its parts moved to their respective domains.
3.  **Vague `database/utils.py`**: The `src/egregora/database/utils.py` module may contain generic SQL utilities, but it could also hide domain-specific query logic that should be part of a specific repository or data access layer.
4.  **Misplaced `text.py`**: The `src/egregora/utils/text.py` module contains a `sanitize_prompt_input` function, which is clearly LLM-related and should be moved to the `src/egregora/llm` module.

## Prioritized Improvements

1.  **`text.py` Refactoring (High Impact, Low Risk)**: Moving `sanitize_prompt_input` is a small, safe change that clearly improves the organization.
2.  **`fs.py` Refactoring (Medium Impact, Low Risk)**: Moving these utilities will likely involve updating a few import sites, but it will significantly clarify the responsibilities of the modules that use them.
3.  **`cache.py` Refactoring (High Impact, Medium Risk)**: This is a high-impact change because it will make the caching strategy much clearer. It's medium risk because it may require careful analysis to ensure the correct caching logic is moved to the correct domain.
4.  **`database/utils.py` Refactoring (Medium Impact, Medium Risk)**: This could improve the data access layer, but requires careful analysis to avoid breaking database interactions.

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

## Organizational Strategy

My strategy is to systematically dismantle the `src/egregora/utils` directory by moving its modules to their correct, domain-specific locations. I will follow a test-driven approach for each move, ensuring that a safety net of tests exists before any code is relocated. Each refactoring will be a single, cohesive change delivered in its own pull request. I will prioritize changes that offer the most significant improvement in clarity for the lowest risk and effort.
