---
id: 20251231-023853-refactor-configuration-management
status: todo
title: "Refactor Configuration Management"
created_at: "2025-12-31T02:38:53Z"
target_module: "src/egregora/orchestration/pipelines/write.py"
assigned_persona: "refactor"
---

## Description

The configuration management logic in `src/egregora/orchestration/pipelines/write.py` is currently spread across multiple functions, including `_prepare_write_config`, `_resolve_write_options`, `run_cli_flow`, and `process_whatsapp_export`. This makes the code difficult to understand, maintain, and test.

This task involves consolidating all configuration-related logic into a new, dedicated module: `src/egregora/orchestration/config_factory.py`.

## Context

This refactoring is the first step in a larger effort to decompose the monolithic `write.py` orchestrator. By isolating configuration management, we can simplify the main pipeline logic and improve the overall structure of the codebase. This change will make it easier to add new configuration options and manage different runtime environments in the future.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor configuration management
def _prepare_write_config(
    options: WriteCommandOptions, from_date_obj: date_type | None, to_date_obj: date_type | None
) -> Any:
    """Prepare Egregora configuration from options."""
    base_config = load_egregora_config(options.output)
    # ...
```
