---
id: "20251231-120658-refactor-data-conversion-utility"
status: todo
title: "Refactor data conversion block to a separate utility function"
created_at: "2025-12-31T12:06:58+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The data conversion block in `_process_single_window` is responsible for converting an Ibis table (or potentially other types) into a Python list. This logic is complex due to its use of nested try-except blocks to handle different data structures.

## Context

This complex inline logic makes the `_process_single_window` function harder to read and maintain. Extracting this into a dedicated utility function will improve clarity, isolate the conversion logic, and make it easier to test.

## Code Snippet

```python
# Convert table to list for command processing
try:
    messages_list = enriched_table.execute().to_pylist()
except (AttributeError, TypeError):
    try:
        messages_list = enriched_table.to_pylist()
    except (AttributeError, TypeError):
        messages_list = enriched_table if isinstance(enriched_table, list) else []
```
