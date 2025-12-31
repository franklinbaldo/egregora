---
id: "20251231-001454-refactor-duplicated-rate-limiting-logic"
status: todo
title: "Refactor duplicated rate-limiting logic into a context manager"
created_at: "2025-12-31T00:14:54Z"
target_module: "src/egregora/llm/providers/rate_limited.py"
assigned_persona: "refactor"
---

## Description

The `request` and `request_stream` methods in `RateLimitedModel` both contain the same `limiter.acquire()` and `limiter.release()` logic. This code is duplicated and can be refactored into a reusable async context manager to improve maintainability and reduce redundancy.

## Context

The current implementation is functional but not optimal. Consolidating the rate-limiting logic will make the code cleaner and easier to reason about.

## Code Snippet

```python
# TODO: [Taskmaster] Refactor duplicated rate-limiting logic into a context manager.
async def request(
    self,
    messages: list[ModelMessage],
    model_settings: ModelSettings | None,
    model_request_parameters: ModelRequestParameters,
) -> ModelResponse:
    """Make a rate-limited request."""
    limiter = get_rate_limiter()
    # ...
    limiter.acquire()
    try:
        return await self.wrapped_model.request(messages, model_settings, model_request_parameters)
    finally:
        limiter.release()

@asynccontextmanager
async def request_stream(
    # ...
) -> AsyncIterator[ModelResponse]:
    """Make a rate-limited stream request."""
    limiter = get_rate_limiter()
    limiter.acquire()
    try:
        # ...
    finally:
        limiter.release()
```
