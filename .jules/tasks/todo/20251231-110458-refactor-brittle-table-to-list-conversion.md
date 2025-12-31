---
id: "20251231-110458-refactor-brittle-table-to-list-conversion"
status: todo
title: "Refactor Brittle Table-to-List Conversion Logic"
created_at: "2025-12-31T11:04:58Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_process_single_window` method in `src/egregora/orchestration/runner.py` contains a brittle, nested `try-except` block to convert a table object into a list. This is a code smell that indicates an unpredictable data structure is being passed around.

## Context

This fragile logic makes the code difficult to maintain and debug. The root cause should be investigated to ensure that a consistent data type is always returned from the upstream enrichment process, removing the need for this defensive coding.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor this brittle conversion logic.
# This nested try-except block is a code smell, suggesting an unpredictable
# data structure. The underlying issue should be fixed to ensure a consistent
# table object is always returned.
# Convert table to list for command processing
try:
    messages_list = enriched_table.execute().to_pylist()
except (AttributeError, TypeError):
    try:
        messages_list = enriched_table.to_pylist()
    except (AttributeError, TypeError):
        messages_list = enriched_table if isinstance(enriched_table, list) else []
```
