---
id: "20251231-080801-refactor-brittle-data-conversion"
status: todo
title: "Refactor brittle data conversion logic to be more robust"
created_at: "2025-12-31T08:08:01Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The logic for converting the `enriched_table` to a list of messages in `_process_single_window` is brittle. It relies on nested `try-except` blocks to handle different potential object types, which indicates an unstable or unclear interface.

## Context

This code should be refactored to use a more reliable method for data conversion. This might involve creating a dedicated utility function or using a more consistent data access pattern. The goal is to remove the `try-except` blocks and make the code more predictable.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor brittle data conversion logic to be more robust.
# Convert table to list for command processing
try:
    messages_list = enriched_table.execute().to_pylist()
except (AttributeError, TypeError):
    try:
        messages_list = enriched_table.to_pylist()
    except (AttributeError, TypeError):
        messages_list = enriched_table if isinstance(enriched_table, list) else []
```
