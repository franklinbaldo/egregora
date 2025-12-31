---
id: "20251231-080735-refactor-process-single-window"
status: todo
title: "Refactor `_process_single_window` to simplify and separate concerns"
created_at: "2025-12-31T08:07:35Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_single_window` method in `PipelineRunner` is responsible for too many tasks, including media processing, data enrichment, command extraction, and post generation. This violates the Single Responsibility Principle and makes the method difficult to test and maintain.

## Context

This method should be refactored into a series of smaller, more focused functions. Each new function should handle a distinct part of the process, such as `_handle_media`, `_run_enrichment`, `_process_commands`, and `_generate_posts`. This will improve modularity, readability, and testability.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor `_process_single_window` to simplify and separate concerns.
def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
    """Process a single window with media extraction, enrichment, and post writing."""
    # ... (very long method body)
```
