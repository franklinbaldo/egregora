---
id: "20251231-140546-refactor-hardcoded-token-limit"
status: todo
title: "Refactor hardcoded 1M token limit into a named constant"
created_at: "2025-12-31T14:05:46Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_resolve_context_token_limit` method in `src/egregora/orchestration/runner.py` contains a hardcoded magic number (`1_048_576`) for the maximum token limit. This should be replaced with a named constant to improve readability and maintainability.

## Context

Hardcoded values make the code harder to understand and update. By using a constant, we provide a clear name for the value's purpose and a single place to change it if needed.

## Code Snippet

```python
def _resolve_context_token_limit(self) -> int:
    """Resolve the effective context window token limit."""
    # TODO: [Taskmaster] Refactor hardcoded 1M token limit into a named constant
    config = self.context.config
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)

    if use_full_window:
        return 1_048_576

    return config.pipeline.max_prompt_tokens
```
