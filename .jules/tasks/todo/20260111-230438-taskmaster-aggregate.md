id: 20260111-230438-taskmaster-aggregate
status: todo
title: "Taskmaster Run: src/egregora/agents/avatar.py"
created_at: "2026-01-11T23:04:38Z"
target_module: "src/egregora/agents/avatar.py"
assigned_persona: "taskmaster"
---

## Summary

This Taskmaster run analyzed `src/egregora/agents/avatar.py` and identified several opportunities for refactoring to improve code quality, maintainability, and configuration management. The key issues found include hardcoded constants, a highly complex function, mixed concerns in another function, brittle fallback logic, and overly broad exception handling.

## Identified Tasks

### 1. Externalize Hardcoded Configuration
- **Description**: Several constants (e.g., `MAX_AVATAR_SIZE_BYTES`, `DEFAULT_DOWNLOAD_TIMEOUT`, `SUPPORTED_IMAGE_EXTENSIONS`) are hardcoded at the module level. These should be moved to a dedicated configuration module or settings object to improve maintainability.
- **Location**: `src/egregora/agents/avatar.py:45` (approximate)
- **Context**: Hardcoding configuration values makes them difficult to change and track. Centralizing them allows for easier management and environment-specific overrides.
- **Suggested Persona**: `refactor`

### 2. Decompose Complex Download Function
- **Description**: The `download_avatar_from_url` function is overly complex, handling URL validation, HTTP requests, content validation, and file saving in a single block. It should be decomposed into smaller, single-responsibility helper functions.
- **Location**: `src/egregora/agents/avatar.py:291` (approximate)
- **Context**: Large, complex functions are difficult to read, test, and maintain. Breaking them down improves modularity and reduces cognitive load.
- **Suggested Persona**: `refactor`

### 3. Separate Concerns in Enrichment Function
- **Description**: The `_enrich_avatar` function mixes several responsibilities: checking the cache, rendering a Jinja prompt, initializing a Pydantic AI agent, and executing the enrichment logic. These concerns should be separated into distinct functions.
- **Location**: `src/egregora/agents/avatar.py:372` (approximate)
- **Context**: Functions that adhere to the Single Responsibility Principle are easier to understand, test, and reuse. This refactoring will improve the separation of caching, presentation, and business logic.
- **Suggested Persona**: `refactor`

### 4. Refactor Brittle MIME Type Fallback
- **Description**: The `_get_extension_from_mime_type` function falls back to `_validate_image_format(url or ".jpg")`. This is brittle because it assumes `.jpg` if the URL is also missing and doesn't consider the actual file content.
- **Location**: `src/egregora/agents/avatar.py:218` (approximate)
- **Context**: The current fallback logic can lead to incorrect file extensions. A more robust approach would be to inspect the file's magic bytes if the MIME type is ambiguous or missing.
- **Suggested Persona**: `refactor`

### 5. Refine Broad Exception Handling
- **Description**: The `_enrich_avatar` function uses a broad `except (httpx.HTTPError, OSError, ValueError, RuntimeError)` block. This should be refined to catch more specific exceptions where possible, providing better error diagnostics.
- **Location**: `src/egregora/agents/avatar.py:454` (approximate)
- **Context**: Catching broad exceptions can hide underlying issues and make debugging difficult. More specific exception handling improves the robustness and reliability of the code.
- **Suggested Persona**: `refactor`
