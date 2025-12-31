---
id: "20251231-120715-refactor-background-task-processing"
status: todo
title: "Refactor background task processing to be more generic"
created_at: "2025-12-31T12:07:15+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `process_background_tasks` function in the `PipelineRunner` class currently instantiates and runs each worker (BannerWorker, ProfileWorker, EnrichmentWorker) sequentially. This approach is repetitive and requires modification each time a new worker is added.

## Context

Refactoring this to a more generic, data-driven approach would improve maintainability. Instead of hardcoding each worker, we could define a list of worker classes and iterate through them, calling a common interface (e.g., a `run` method) on each. This would make the system more extensible and reduce code duplication.

## Code Snippet

```python
def process_background_tasks(self) -> None:
    """Process pending background tasks."""
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
