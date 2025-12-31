---
id: "20251231-080648-refactor-process-windows-clarity"
status: todo
title: "Refactor `process_windows` to improve clarity and separation of concerns"
created_at: "2025-12-31T08:06:48Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `process_windows` method in `PipelineRunner` is overly complex, mixing setup, iteration logic, and result aggregation. This makes the control flow difficult to follow and maintain.

## Context

This method is the main entry point for the window processing loop. Its current structure makes it hard to test individual parts of the logic (e.g., window validation, result handling) in isolation.

Refactoring this method to use smaller helper functions would improve readability, testability, and overall code quality.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor `process_windows` to improve clarity and separation of concerns.
def process_windows(
    self,
    windows_iterator: Any,
) -> tuple[dict[str, dict[str, list[str]]], datetime | None]:
    """Process all windows with tracking and error handling."""
    # ... (long method body)
```
