---
id: "20251231-131509-replace-magic-number-with-constant"
status: todo
title: "Replace magic number with a named constant"
created_at: "2025-12-31T13:15:20Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

### Description

The `_resolve_context_token_limit` method in `PipelineRunner` uses a hardcoded magic number (`1_048_576`) to represent the full context window size. This makes the code harder to read and maintain.

### Context

Replacing this magic number with a well-named constant will improve code clarity and make it easier to update the value in the future if the model's context window changes. This is a small but important change that contributes to overall code quality.

### Code Snippet

```python
def _resolve_context_token_limit(self) -> int:
    """Resolve the effective context window token limit."""
    config = self.context.config
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)

    # TODO: [Taskmaster] Replace magic number with a named constant
    if use_full_window:
        return 1_048_576

    return config.pipeline.max_prompt_tokens
```
