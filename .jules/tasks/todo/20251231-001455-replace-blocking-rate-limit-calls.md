---
id: "20251231-001455-replace-blocking-rate-limit-calls"
status: todo
title: "Replace blocking acquire/release with a non-blocking alternative"
created_at: "2025-12-31T00:14:55Z"
target_module: "src/egregora/llm/providers/rate_limited.py"
assigned_persona: "refactor"
---

## Description

The `limiter.acquire()` call in the `request` and `request_stream` methods is a synchronous, blocking call. Since these methods are `async`, this could potentially block the event loop, leading to performance issues. The implementation should be updated to use a non-blocking alternative for acquiring and releasing the rate limit semaphore.

## Context

The comments in the code indicate awareness of this issue. A proper fix would involve using an `async` version of the semaphore or running the blocking call in a separate thread to avoid stalling the event loop.

## Code Snippet

```python
# TODO: [Taskmaster] Replace blocking acquire/release with a non-blocking alternative.
limiter.acquire()
try:
    return await self.wrapped_model.request(messages, model_settings, model_request_parameters)
finally:
    limiter.release()
```
