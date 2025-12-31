---
id: 20251231-024020-decompose-pipeline-preparation
status: todo
title: "Decompose Pipeline Preparation Logic"
created_at: "2025-12-31T02:40:20Z"
target_module: "src/egregora/orchestration/pipelines/write.py"
assigned_persona: "refactor"
---

## Description

The `_prepare_pipeline_data` function in `src/egregora/orchestration/pipelines/write.py` has grown too large and complex. It is responsible for a wide range of tasks, including parsing input data, applying filters, creating message windows, and initializing the RAG index. This violates the Single Responsibility Principle and makes the function difficult to understand, test, and maintain.

This task involves breaking down `_prepare_pipeline_data` into several smaller, more focused functions, each responsible for a distinct step in the pipeline preparation process.

## Context

This is a key part of the larger effort to refactor the `write.py` orchestrator. Decomposing this function will significantly improve the clarity and modularity of the pipeline's data preparation stage. It will create a more logical flow and make it easier to modify or extend the preparation steps in the future.

## Code Snippet

```python
# TODO: [Taskmaster] Decompose pipeline preparation logic
def _prepare_pipeline_data(
    adapter: any,
    run_params: PipelineRunParams,
    ctx: PipelineContext,
) -> PreparedPipelineData:
    """Prepare messages, filters, and windowing context for processing."""
    # ...
```
