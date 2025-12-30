---
id: 20251230-200541-refactor-rate-limited-model-for-non-blocking-acquisition
status: todo
title: "Refactor RateLimitedModel for Non-Blocking Acquisition"
created_at: "2025-12-30T20:05:41Z"
target_module: "src/egregora/llm/providers/rate_limited.py"
assigned_persona: "refactor"
---

## Description

The `RateLimitedModel` class in `src/egregora/llm/providers/rate_limited.py` uses a blocking `limiter.acquire()` call within its `async` methods (`request` and `request_stream`). This can block the entire event loop, leading to performance issues.

## Context

The current implementation was designed with a synchronous execution model in mind, but since `pydantic-ai` calls these methods asynchronously, the blocking call is problematic. The goal is to refactor the rate limit acquisition to be non-blocking, for example by using `asyncio.to_thread` (in Python 3.9+) or a similar mechanism.

## Code Snippet

```python
# src/egregora/llm/providers/rate_limited.py

class RateLimitedModel(Model):
    # ...
    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a rate-limited request."""
        limiter = get_rate_limiter()

        # ... (comments)

        # TODO: [Taskmaster] Refactor to use non-blocking rate limit acquisition
        limiter.acquire()  # <-- This is a blocking call
        try:
            return await self.wrapped_model.request(messages, model_settings, model_request_parameters)
        finally:
            limiter.release()
```
