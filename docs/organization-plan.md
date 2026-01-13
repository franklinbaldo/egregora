# Codebase Organization Plan

Last updated: 2026-01-06

## Current Organizational State

The codebase is generally well-structured, with a clear separation of concerns between domains like `llm`, `knowledge`, `orchestration`, and `output_adapters`. The generic `src/egregora/utils` directory, which previously served as a "junk drawer," has been significantly cleaned up, with most domain-specific logic moved to its proper home.

The testing structure largely mirrors the source structure, which is good.

## Identified Issues

*No outstanding organizational issues have been identified at this time. The plan needs to be updated with a new discovery phase.*

## Prioritized Improvements

*Priorities will be re-evaluated after the next discovery phase.*

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
- **Removed dead code from `database/utils.py`**
- **Removed dead compatibility shims from `utils` (`cache.py`, `authors.py`)**
- **Removed dead compatibility shims from `utils` (`exceptions.py`)**


## Organizational Strategy

My strategy is to systematically dismantle the `src/egregora/utils` directory by moving its modules to their correct, domain-specific locations. I will follow a test-driven approach for each move, ensuring that a safety net of tests exists before any code is relocated. Each refactoring will be a single, cohesive change delivered in its own pull request. I will prioritize changes that offer the most significant improvement in clarity for the lowest risk and effort. The next session should begin with a discovery phase to identify new refactoring opportunities.
