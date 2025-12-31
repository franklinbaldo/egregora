---
id: 20251231-024057-simplify-run-entry-points
status: todo
title: "Simplify CLI and Main Run Entry Points"
created_at: "2025-12-31T02:40:57Z"
target_module: "src/egregora/orchestration/pipelines/write.py"
assigned_persona: "refactor"
---

## Description

The `run_cli_flow` and `run` functions in `src/egregora/orchestration/pipelines/write.py` are currently responsible for a large amount of the orchestration logic. `run_cli_flow` handles argument parsing, validation, and configuration merging, while `run` orchestrates the entire pipeline execution.

This task is to refactor both functions to delegate their responsibilities to the newly proposed modules for configuration (`config_factory.py`), resource management (`resources.py`), and the decomposed pipeline preparation steps.

## Context

This is the final step in the initial decomposition of the monolithic `write.py` orchestrator. By simplifying these primary entry points, we will make the pipeline's overall execution flow clearer and more maintainable. The goal is for these functions to act as simple coordinators, rather than carrying out the complex logic themselves.

## Code Snippets

```python
# TODO: [Taskmaster] Simplify CLI and main run entry points
def run_cli_flow(
    input_file: Path,
    *,
    # ...
):
```

```python
def run(run_params: PipelineRunParams) -> dict[str, dict[str, list[str]]]:
    # TODO: [Taskmaster] Simplify CLI and main run entry points
    """Run the complete write pipeline workflow."""
    # ...
```
