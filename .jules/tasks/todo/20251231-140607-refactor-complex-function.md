---
id: "20251231-140607-refactor-complex-function"
status: todo
title: "Refactor complex function into smaller, single-responsibility functions"
created_at: "2025-12-31T14:06:07Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_single_window` method in `src/egregora/orchestration/runner.py` has grown too large and complex. It currently handles media processing, data enrichment, command processing, post generation, and profile generation.

## Context

To improve readability, testability, and maintainability, this method should be broken down into several smaller functions, each with a single, clear responsibility.

## Code Snippet

```python
def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
    # TODO: [Taskmaster] Refactor complex function into smaller, single-responsibility functions
    """Process a single window with media extraction, enrichment, and post writing."""
    indent = "  " * depth
    window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"
```
