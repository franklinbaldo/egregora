---
id: "20251231-060709-refactor-complex-method"
status: todo
title: "Refactor complex method with multiple responsibilities"
created_at: "2025-12-31T06:07:21Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## 📋 Refactor Complex Method with Multiple Responsibilities

**Context:**
The `_process_single_window` method in `src/egregora/orchestration/runner.py` is overly complex and has too many responsibilities. It handles media processing, enrichment, command extraction, and post generation, making it difficult to understand and maintain.

**Task:**
- Break down the `_process_single_window` method into smaller, more focused functions.
- Each new function should have a single, well-defined responsibility.

**Code Snippet:**
```python
# src/egregora/orchestration/runner.py

    def _process_single_window(self, window: Any, *, depth: int = 0) -> dict[str, dict[str, list[str]]]:
        # TODO: [Taskmaster] Refactor complex method with multiple responsibilities
        """Process a single window with media extraction, enrichment, and post writing."""
        indent = "  " * depth
        window_label = f"{window.start_time:%Y-%m-%d %H:%M} to {window.end_time:%H:%M}"

        logger.info("%s➡️  [bold]%s[/] — %s messages (depth=%d)", indent, window_label, window.size, depth)

        output_sink = self.context.output_format
        if output_sink is None:
            raise OutputSinkError("Output adapter must be initialized before processing windows.")
        # ... and so on
```
