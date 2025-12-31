---
id: "20251231-110459-replace-magic-number-for-token-limit"
status: todo
title: "Replace Magic Number for Full Context Token Limit"
created_at: "2025-12-31T11:04:58Z"
target_module: "src/egregora/orchestration/runner.py"
assigned_persona: "refactor"
---

## Description

The `_resolve_context_token_limit` method in `src/egregora/orchestration/runner.py` uses the hardcoded "magic number" `1_048_576` to represent the full context window size for the language model.

## Context

Using unnamed magic numbers makes the code harder to read and maintain. This value should be defined as a named constant in a suitable location, such as an `egregora.llm.constants` module, and then imported for use. This improves clarity and makes the value easier to update if the model's context window changes.

## Code Snippet

```python
# TODO: [Taskmaster] Replace magic number with a named constant
# Hardcoding this value makes it difficult to maintain. It should
# be defined as a constant in a relevant module (e.g., `egregora.llm.constants`)
# and imported here.
return 1_048_576
```
