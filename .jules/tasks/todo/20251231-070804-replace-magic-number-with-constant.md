---
id: 20251231-070804-replace-magic-number-with-constant
status: todo
title: "Replace Magic Number with Named Constant in `_resolve_context_token_limit`"
created_at: "2025-12-31T07:08:04Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

### Description

The `_resolve_context_token_limit` method in `PipelineRunner` uses the hardcoded value `1_048_576` to represent the maximum token limit for the full context window. This "magic number" makes the code harder to understand, as the value's significance is not immediately clear.

### Task

Replace the hardcoded value `1_048_576` with a named constant (e.g., `FULL_CONTEXT_WINDOW_TOKEN_LIMIT`). The constant should be defined at the module level to provide a clear, descriptive name for the value.

### Rationale

Using a named constant will improve code readability and maintainability by making the purpose of the value explicit and providing a single, easy-to-find location for future updates.
