---
id: 20251230-210437-refactor-rate-limited-model-for-non-blocking-calls
status: todo
title: "Refactor RateLimitedModel for Non-Blocking Calls"
created_at: "2025-12-30T21:04:37Z"
target_module: "src/egregora/llm/providers/rate_limited.py"
assigned_persona: "refactor"
---

## Description

The `RateLimitedModel.request` method in `src/egregora/llm/providers/rate_limited.py` is an `async` method, but it contains a synchronous, blocking call: `limiter.acquire()`.

This poses a risk of blocking the entire asyncio event loop, which can degrade performance and lead to unexpected behavior in an asynchronous application.

## Task

Refactor the `request` method to ensure that the rate limiter's lock acquisition is non-blocking. This might involve:
- Using an asynchronous rate-limiting library.
- Wrapping the synchronous call in `asyncio.to_thread` (in Python 3.9+) or a similar executor-based approach to avoid blocking the main thread.

## Code Snippet
```python
# src/egregora/llm/providers/rate_limited.py

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a rate-limited request."""
        limiter = get_rate_limiter()

        # ... (comments)

        # TODO: [Taskmaster] Refactor to be non-blocking in async context
        limiter.acquire()  # <-- This is a blocking call
        try:
            return await self.wrapped_model.request(messages, model_settings, model_request_parameters)
        finally:
            limiter.release()
```
