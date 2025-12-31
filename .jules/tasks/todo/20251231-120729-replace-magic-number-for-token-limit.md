---
id: "20251231-120729-replace-magic-number-for-token-limit"
status: todo
title: "Replace magic number for token limit with a named constant"
created_at: "2025-12-31T12:07:29+00:00"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_resolve_context_token_limit` function in the `PipelineRunner` class contains a hardcoded magic number, `1_048_576`, representing the full context window size. This number lacks semantic meaning and can be confusing to future maintainers.

## Context

Using a named constant (e.g., `FULL_CONTEXT_WINDOW_TOKENS`) instead of a magic number will improve code readability and maintainability. It makes the code self-documenting and provides a single point of reference if this value ever needs to be changed.

## Code Snippet

```python
def _resolve_context_token_limit(self) -> int:
    """Resolve the effective context window token limit."""
    config = self.context.config
    use_full_window = getattr(config.pipeline, "use_full_context_window", False)

    if use_full_window:
        return 1_048_576

    return config.pipeline.max_prompt_tokens
```
