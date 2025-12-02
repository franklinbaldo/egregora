"""Rate limited model wrapper for pydantic-ai models."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings

from egregora.utils.rate_limit import get_rate_limiter

logger = logging.getLogger(__name__)


class RateLimitedModel(Model):
    """Wraps a pydantic-ai Model to enforce global rate limits."""

    def __init__(self, wrapped_model: Model) -> None:
        self.wrapped_model = wrapped_model

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a rate-limited request."""
        limiter = get_rate_limiter()
        
        # Acquire slot (blocks if needed)
        # Note: limiter.acquire() is blocking (sync). 
        # Since we are in async method, this blocks the event loop if not careful.
        # But we are moving to synchronous execution mostly.
        # However, pydantic-ai Agent calls this async method.
        # If we block here, we block the loop.
        # But since we are de-asyncing, maybe we should use run_in_executor?
        # Or just accept blocking if we are running in a thread (run_sync does that).
        
        # If running via agent.run_sync(), we are in a dedicated thread/loop.
        # Blocking here is fine.
        
        limiter.acquire()
        try:
            return await self.wrapped_model.request(
                messages, model_settings, model_request_parameters
            )
        finally:
            limiter.release()

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[ModelResponse]:
        """Make a rate-limited stream request."""
        limiter = get_rate_limiter()
        limiter.acquire()
        try:
            async with self.wrapped_model.request_stream(
                messages, model_settings, model_request_parameters
            ) as stream:
                yield stream
        finally:
            limiter.release()

    @property
    def model_name(self) -> str:
        return self.wrapped_model.model_name

    @property
    def system(self) -> str | None:
        return self.wrapped_model.system
