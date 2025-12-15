"""Rate limited model wrapper for pydantic-ai models."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

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
        model_name = self.model_name
        limiter = get_rate_limiter()

        # Time the rate limiter acquisition
        t0 = time.perf_counter()
        limiter.acquire()
        t1 = time.perf_counter()
        acquire_time = (t1 - t0) * 1000  # ms
        if acquire_time > 100:  # Log if waited more than 100ms
            logger.info("[RateLimited] %s: waited %.0fms for rate limiter", model_name, acquire_time)

        try:
            t2 = time.perf_counter()
            logger.debug("[RateLimited] %s: starting request", model_name)
            response = await self.wrapped_model.request(messages, model_settings, model_request_parameters)
            t3 = time.perf_counter()
            logger.debug("[RateLimited] %s: request completed in %.0fms", model_name, (t3 - t2) * 1000)
            return response
        except Exception as e:
            t3 = time.perf_counter()
            logger.info("[RateLimited] %s: request failed after %.0fms: %s", model_name, (t3 - t2) * 1000, str(e)[:80])
            raise
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
