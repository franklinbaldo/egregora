# Codebase Organization Plan

Last updated: 2024-07-25

## Current Organizational State

The codebase contains a `src/egregora/text_processing` directory with a single module, `chunking.py`. This module provides text chunking functionality. This has been addressed in the latest improvement.

## Identified Issues

*   **Misplaced Responsibility:** The `simple_chunk_text` function in `src/egregora/text_processing/chunking.py` is only used by the Retrieval-Augmented Generation (RAG) components in `src/egregora/rag/` and `src/egregora_v3/infra/rag.py`. This violates the principle of co-location, as the chunking logic is tightly coupled to the RAG domain but resides in a generic utility directory. The `text_processing` directory itself seems redundant if this is its only content.

## Prioritized Improvements

*None at the moment.*

## Completed Improvements

*   **Co-locate Chunking Logic with RAG:** Moved the chunking functionality from the generic `text_processing` module into the `rag` module. This improves modularity and makes the codebase easier to understand by placing domain-specific logic where it is used.
*   **Refactored `UsageTracker` to `src/egregora/llm/usage.py`:** Co-located LLM usage tracking logic with other LLM-related code.
*   **Removed duplicated `run_async_safely` function:** Eliminated dead, duplicated code from the orchestration pipeline.
*   **Refactored `datetime` utilities:** Moved domain-specific datetime functions from generic utils to the `mkdocs` output adapter.
*   **Refactor Site Scaffolding:** Eliminated a redundant and confusing compatibility layer for site initialization.
*   **Refactored `Rate_Limiter` to `llm` module:** Co-located the LLM rate-limiting logic with other LLM-related code.
*   **Refactored `Slugify` Utility:** Moved the `slugify` function from `utils/paths.py` to `utils/text.py` to better reflect its purpose.
*   **Refactored API Key Utilities:** Moved API key management functions from generic utils to the `llm` module.
*   **Removed Orphaned Infra Directory:** Removed an empty and unused `src/egregora/infra` directory.

## Organizational Strategy

My strategy is to improve the modularity and navigability of the codebase by moving domain-specific logic out of generic utility modules and into the modules that use them. This follows the principle of co-location and the Single Responsibility Principle. I will use a Test-Driven Development (TDD) approach to ensure that all refactoring is safe and does not introduce regressions.
