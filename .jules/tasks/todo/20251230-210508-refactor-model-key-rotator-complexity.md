---
id: 20251230-210508-refactor-model-key-rotator-complexity
status: todo
title: "Refactor ModelKeyRotator for Clarity and Reduced Complexity"
created_at: "2025-12-30T21:05:08Z"
target_module: "src/egregora/llm/providers/model_key_rotator.py"
assigned_persona: "refactor"
---

## Description

The `call_with_rotation` method in `src/egregora/llm/providers/model_key_rotator.py` has a high cyclomatic complexity. The nested loops, multiple exit points, and complex exception handling make it difficult to understand, maintain, and test.

The current implementation mixes the logic for key rotation and model rotation within a single `while True:` loop, which obscures the flow of control.

## Task

Refactor the `call_with_rotation` method to improve its clarity and reduce its complexity. Potential strategies include:
- Decomposing the method into smaller, more focused helper functions (e.g., a function to handle all keys for a single model).
- Using more descriptive variable names.
- Simplifying the control flow, perhaps by removing the `while True` loop in favor of a more explicit structure.
- Adding more comments to explain the rotation strategy.

## Code Snippet
```python
# src/egregora/llm/providers/model_key_rotator.py

    # TODO: [Taskmaster] Refactor for clarity and reduced complexity
    def call_with_rotation(
        self,
        call_fn: Callable[[str, str], Any],
        is_rate_limit_error: Callable[[Exception], bool] | None = None,
    ) -> Any:
        """Call function trying all keys for each model before rotating models."""
        # ... (implementation is complex)
```
