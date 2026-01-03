id: 20260103-013349-taskmaster-enricher-refactor
status: todo
title: "Taskmaster Run: src/egregora/agents/enricher.py"
created_at: "2026-01-03T01:33:49Z"
target_module: "src/egregora/agents/enricher.py"
assigned_persona: "taskmaster"
---

## Summary

The `src/egregora/agents/enricher.py` module is a high-complexity component responsible for both URL and media enrichment. The `EnrichmentWorker` class has grown into a "god object" that violates the Single Responsibility Principle, making it difficult to maintain, test, and reason about. The module also contains brittle logic, security vulnerabilities, and inefficient code patterns.

This ticket aggregates several required refactoring tasks to improve the module's health.

## Identified Tasks

### 1. Decompose EnrichmentWorker into Separate Classes
- **Description**: The `EnrichmentWorker` class should be split into `UrlEnrichmentWorker` and `MediaEnrichmentWorker` to separate concerns and reduce complexity.
- **Location**: `src/egregora/agents/enricher.py:468`
- **Context**: The current class handles too many responsibilities, violating the Single Responsibility Principle. Decomposing it will make the code more modular and easier to understand.
- **Suggested Persona**: refactor

### 2. Refactor the `run` method
- **Description**: The `run` method's logic for fetching tasks, calculating concurrency, and orchestrating batches should be broken down into smaller helper functions.
- **Location**: `src/egregora/agents/enricher.py:539`
- **Context**: The method is currently doing too much, which makes it hard to read and debug. Smaller functions will improve clarity.
- **Suggested Persona**: refactor

### 3. Refactor `_persist_media_results` to Reduce Complexity
- **Description**: The `_persist_media_results` method is overly long and complex. It should be decomposed into smaller functions that handle distinct responsibilities like result parsing, document creation, and database updates.
- **Location**: `src/egregora/agents/enricher.py:1364`
- **Context**: This large method is a maintenance bottleneck. Breaking it down will improve modularity and testability.
- **Suggested Persona**: refactor

### 4. Refactor Single-Call Execution Logic
- **Description**: The `_execute_url_single_call` and `_execute_media_single_call` methods mix concerns like prompt rendering, client creation, and response parsing. This logic should be extracted into dedicated helpers.
- **Location**: `src/egregora/agents/enricher.py:787` and `src/egregora/agents/enricher.py:1172`
- **Context**: Simplifying these methods will improve their readability and make the overall control flow easier to follow.
- **Suggested Persona**: refactor

### 5. Replace Brittle String Cleaning with Robust JSON Parsing
- **Description**: The `_parse_media_result` method uses fragile string manipulation to clean the LLM response before JSON parsing. This should be replaced with a more robust method, like using a regex to extract the JSON block.
- **Location**: `src/egregora/agents/enricher.py:1544`
- **Context**: The current implementation is prone to breaking if the LLM's output format changes slightly. A more robust parsing strategy is needed.
- **Suggested Persona**: refactor

### 6. Use Parameterized Queries to Prevent SQL Injection
- **Description**: The `_persist_media_results` method uses an f-string to construct a SQL query, creating a security risk. This must be refactored to use parameterized queries.
- **Location**: `src/egregora/agents/enricher.py:1519`
- **Context**: Using f-strings for SQL queries is a critical security vulnerability (SQL injection). This needs to be fixed to protect the application.
- **Suggested Persona**: shepherd

### 7. Centralize `genai.Client` Instantiation
- **Description**: The `genai.Client` is instantiated multiple times throughout the file. This should be refactored to use a single factory function or a shared client instance.
- **Location**: `src/egregora/agents/enricher.py:801`
- **Context**: Centralizing client creation avoids redundant code, simplifies configuration management, and improves performance by reusing connections where appropriate.
- **Suggested Persona**: refactor

### 8. Simplify the Async-in-Sync Execution Pattern
- **Description**: The pattern of creating a new asyncio event loop within a thread in `_enrich_single_url` is overly complex. This should be refactored to use a simpler, more standard approach.
- **Location**: `src/egregora/agents/enricher.py:627`
- **Context**: The current implementation is hard to reason about and can be inefficient. A simpler pattern will improve code clarity and maintainability.
- **Suggested Persona**: refactor
