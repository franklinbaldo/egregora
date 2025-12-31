---
id: 20251231-070751-extract-window-splitting-logic
status: todo
title: "Extract Window Splitting Logic from `_process_window_with_auto_split`"
created_at: "2025-12-31T07:07:51Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

### Description

The `_process_window_with_auto_split` method currently contains logic for both iterating through a queue of windows and for splitting a window when a `PromptTooLargeError` is caught. This combination of responsibilities makes the method more complex than necessary.

### Task

Refactor the `_process_window_with_auto_split` method to extract the window-splitting functionality into a new, dedicated helper method. The existing method should be responsible for managing the queue, while the new method should handle the specifics of splitting a window and returning the resulting sub-windows.

### Rationale

Separating these concerns will make both the queue management and the window-splitting logic easier to understand, test, and maintain.
