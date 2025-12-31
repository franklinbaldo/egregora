---
id: "20251231-060709-refactor-duplicated-worker-logic"
status: todo
title: "Refactor duplicated worker logic"
created_at: "2025-12-31T06:07:21Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## 📋 Refactor Duplicated Worker Logic

**Context:**
The `process_background_tasks` method in `src/egregora/orchestration/runner.py` contains duplicated logic for initializing and running different types of workers (`BannerWorker`, `ProfileWorker`, `EnrichmentWorker`).

**Task:**
- Abstract the worker initialization and execution logic to a more generic function or class.
- This will reduce code duplication and make it easier to add new worker types in the future.

**Code Snippet:**
```python
# src/egregora/orchestration/runner.py

    def process_background_tasks(self) -> None:
        # TODO: [Taskmaster] Refactor duplicated worker logic
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
