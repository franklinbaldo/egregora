---
id: "20251231-110500-refactor-background-task-processing"
status: todo
title: "Refactor Background Task Processing with Dynamic Worker Discovery"
created_at: "2025-12-31T11:04:58Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `process_background_tasks` method in `src/egregora/orchestration/runner.py` manually instantiates and runs each background worker (`BannerWorker`, `ProfileWorker`, `EnrichmentWorker`). This implementation is rigid and requires manual code changes whenever a new worker is added or removed.

## Context

To improve modularity and maintainability, this method should be refactored to use a dynamic worker discovery mechanism. For example, workers could be registered in a central registry or discovered by inspecting a specific module or directory. This would create a more flexible and extensible system.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor to use a dynamic worker discovery mechanism.
# This current implementation is rigid. A better approach would be to
# dynamically discover and instantiate worker classes from a registry
# or a specific module, rather than hardcoding each one.
banner_worker = BannerWorker(self.context)
banners_processed = banner_worker.run()
# ... and so on for other workers
```
