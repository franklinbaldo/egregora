---
id: "20251231-080711-optimize-worker-instantiation"
status: todo
title: "Refactor `process_background_tasks` to avoid re-instantiating workers on every call"
created_at: "2025-12-31T08:07:11Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `process_background_tasks` method in `PipelineRunner` instantiates new `BannerWorker`, `ProfileWorker`, and `EnrichmentWorker` objects on every invocation. This is inefficient as this method is called within the main window processing loop.

## Context

These workers can be instantiated once and reused across multiple calls. Refactoring this to create the workers in the `__init__` method of `PipelineRunner` and storing them as instance attributes will improve performance by reducing unnecessary object creation.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor `process_background_tasks` to avoid re-instantiating workers on every call.
def process_background_tasks(self) -> None:
    """Process pending background tasks."""
    if not hasattr(self.context, "task_store") or not self.context.task_store:
        return

    logger.info("⚙️  [bold cyan]Processing background tasks...[/]")

    banner_worker = BannerWorker(self.context)
    # ...
    profile_worker = ProfileWorker(self.context)
    # ...
    enrichment_worker = EnrichmentWorker(self.context)
    # ...
```
