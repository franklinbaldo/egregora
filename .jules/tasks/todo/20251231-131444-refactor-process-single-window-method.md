---
id: "20251231-131444-refactor-process-single-window-method"
status: todo
title: "Refactor _process_single_window into smaller functions"
created_at: "2025-12-31T13:14:54Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

### Description

The `_process_single_window` method in `PipelineRunner` has grown too large and complex. It currently handles media processing, data enrichment, command extraction, post generation, and profile creation, violating the Single Responsibility Principle.

### Context

This refactoring is essential for improving the maintainability and testability of the orchestration logic. By breaking the method down into smaller, single-purpose functions, the code will become more modular, easier to understand, and less prone to bugs. This is part of a broader initiative to enhance the overall health of the codebase.

### Code Snippet

```python
def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
    # TODO: [Taskmaster] Refactor this method into smaller, single-responsibility functions
    """Process a single window with media extraction, enrichment, and post writing."""
    indent = "  " * depth
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
    # ... more code
```
