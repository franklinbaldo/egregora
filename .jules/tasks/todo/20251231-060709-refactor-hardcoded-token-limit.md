---
id: "20251231-060709-refactor-hardcoded-token-limit"
status: todo
title: "Refactor hardcoded magic number for token limit"
created_at: "2025-12-31T06:07:21Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## 📋 Refactor Hardcoded Magic Number for Token Limit

**Context:**
The `_resolve_context_token_limit` method in `src/egregora/orchestration/runner.py` contains a hardcoded magic number (`1_048_576`) for the full context window token limit. This makes the code harder to read and maintain.

**Task:**
- Replace the magic number with a named constant to improve clarity and maintainability.
- The constant should be defined at the module level.

**Code Snippet:**
```python
# src/egregora/orchestration/runner.py

    def _resolve_context_token_limit(self) -> int:
        """Resolve the effective context window token limit."""
        config = self.context.config
        use_full_window = getattr(config.pipeline, "use_full_context_window", False)

        if use_full_window:
            # TODO: [Taskmaster] Refactor hardcoded magic number for token limit
            return 1_048_576

        return config.pipeline.max_prompt_tokens
```
