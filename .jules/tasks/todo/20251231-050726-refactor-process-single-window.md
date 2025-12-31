---
id: 20251231-050726-refactor-process-single-window
status: todo
title: "Refactor Overly Complex `_process_single_window` Method"
created_at: "2025-12-31T05:07:33+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_single_window` method in `PipelineRunner` is overly complex and handles too many responsibilities. It is responsible for media processing, data enrichment, command extraction and execution, and post generation. This makes the method difficult to read, test, and maintain.

## Context

Breaking this method down into smaller, more focused functions would improve modularity and clarity. Each new function should handle a single responsibility, such as media processing or command execution.

## Code Snippet

```python
# src/egregora/orchestration/runner.py

def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
    # TODO: [Taskmaster] Overly complex method
    """Process a single window with media extraction, enrichment, and post writing."""
    indent = "  " * depth
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
    # ... method continues for over 100 lines
```
