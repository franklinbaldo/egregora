---
id: 20251231-023926-isolate-resource-management
status: todo
title: "Isolate Resource Management"
created_at: "2025-12-31T02:39:26Z"
target_module: "src/egregora/orchestration/pipelines/write.py"
assigned_persona: "refactor"
---

## Description

The resource management logic in `src/egregora/orchestration/pipelines/write.py`, specifically the `_create_database_backends` and `_pipeline_environment` functions, handles the setup and teardown of critical resources like database connections. This logic is complex and tightly coupled with the main pipeline orchestration.

This task involves moving all resource management responsibilities into a new, dedicated module: `src/egregora/orchestration/resources.py`.

## Context

This refactoring is the second step in decomposing the monolithic `write.py` orchestrator. By isolating resource management, we can create a clear separation of concerns, making the codebase easier to understand and maintain. This change will also improve testability by allowing resources to be mocked or stubbed out more easily.

## Code Snippet

```python
# TODO: [Taskmaster] Isolate resource management
def _create_database_backends(
    site_root: Path,
    config: EgregoraConfig,
) -> tuple[str, any, any]:
    """Create database backends for pipeline and runs tracking."""
    # ...
```
