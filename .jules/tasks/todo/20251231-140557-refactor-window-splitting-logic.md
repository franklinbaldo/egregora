---
id: "20251231-140557-refactor-window-splitting-logic"
status: todo
title: "Refactor window splitting logic into a separate, focused function"
created_at: "2025-12-31T14:05:57Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_window_with_auto_split` method in `src/egregora/orchestration/runner.py` currently handles both the window processing loop and the logic for splitting a window when a `PromptTooLargeError` occurs. This mixing of concerns makes the method more complex than necessary.

## Context

The window splitting logic should be extracted into its own function. This will simplify `_process_window_with_auto_split` and create a more modular, reusable, and testable piece of code.

## Code Snippet

```python
def _process_window_with_auto_split(
    self, window: Any, *, depth: int = 0, max_depth: int = 5
) -> dict[str, dict[str, list[str]]]:
    # TODO: [Taskmaster] Refactor window splitting logic into a separate, focused function
    """Process a window with automatic splitting if prompt exceeds model limit."""
    min_window_size = 5
    results: dict[str, dict[str, list[str]]] = {}
    queue: deque[tuple[Any, int]] = deque([(window, depth)])
```
