---
id: 20251231-050726-inefficient-worker-instantiation
status: todo
title: "Refactor Inefficient Worker Instantiation in `process_background_tasks`"
created_at: "2025-12-31T05:07:33+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `process_background_tasks` method in `PipelineRunner` instantiates `BannerWorker`, `ProfileWorker`, and `EnrichmentWorker` on every call. This is inefficient as these workers could be initialized once and reused across multiple calls.

## Context

This method is called within a loop in `process_windows`. Creating new worker instances in each iteration adds unnecessary overhead. The workers should be instantiated once in the `PipelineRunner`'s constructor and reused.

## Code Snippet

```python
# src/egregora/orchestration/runner.py

def process_background_tasks(self) -> None:
    """Process pending background tasks."""
    # TODO: [Taskmaster] Inefficient worker instantiation
    if not hasattr(self.context, "task_store") or not self.context.task_store:
        return

    logger.info("⚙️  [bold cyan]Processing background tasks...[/]")

    banner_worker = BannerWorker(self.context)
    banners_processed = banner_worker.run()
    if banners_processed > 0:
        logger.info("Generated %d banners", banners_processed)

    profile_worker = ProfileWorker(self.context)
    profiles_processed = profile_worker.run()
    if profiles_processed > 0:
        logger.info("Updated %d profiles", profiles_processed)

    enrichment_worker = EnrichmentWorker(self.context)
    enrichment_processed = enrichment_worker.run()
    if enrichment_processed > 0:
        logger.info("Enriched %d items", enrichment_processed)
```
