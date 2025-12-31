---
id: 20251231-050726-simplify-data-handling-logic
status: todo
title: "Simplify Complex Data Handling Logic in `_process_single_window`"
created_at: "2025-12-31T05:07:33+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_single_window` method in `PipelineRunner` contains complex logic for converting an `enriched_table` object into a list. It uses nested `try-except` blocks to defensively handle multiple possible data structures (`ibis.Table`, `duckdb.Table`, `list`), which makes the code hard to read and brittle.

## Context

This pattern suggests a lack of a standardized data interface between pipeline components. The logic should be refactored to rely on a consistent data type, which will eliminate the need for nested error handling and make the data flow more predictable.

## Code Snippet

```python
# src/egregora/orchestration/runner.py

# TODO: [Taskmaster] Complex data handling logic
# Convert table to list for command processing
try:
    messages_list = enriched_table.execute().to_pylist()
except (AttributeError, TypeError):
    try:
        messages_list = enriched_table.to_pylist()
    except (AttributeError, TypeError):
        messages_list = enriched_table if isinstance(enriched_table, list) else []
```
