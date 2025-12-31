---
id: 20251231-070732-refactor-process-single-window
status: todo
title: "Refactor `_process_single_window` to Improve Clarity"
created_at: "2025-12-31T07:07:32Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

### Description

The `_process_single_window` method in `PipelineRunner` has grown too complex. It currently handles media processing, enrichment, command extraction, post generation, and profile creation. This mixing of concerns makes the method difficult to read, test, and maintain.

### Task

Refactor the `_process_single_window` method by breaking it down into several smaller, single-responsibility functions. Each new function should handle a distinct part of the process (e.g., one for media, one for enrichment, etc.).

### Rationale

This refactoring will improve code modularity, readability, and testability, making the orchestration logic easier to understand and modify in the future.
