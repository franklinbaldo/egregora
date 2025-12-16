"""Rate limited model wrapper for pydantic-ai models using aiolimiter."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiolimiter import AsyncLimiter
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings

logger = logging.getLogger(__name__)

# Global limiter: 10 requests per second (adjustable)
_global_limiter = AsyncLimiter(max_rate=10.0, time_period=1.0)


def set_global_rate_limit(max_rate: float, time_period: float = 1.0) -> None:
    """Configure the global rate limiter."""
    global _global_limiter
    _global_limiter = AsyncLimiter(max_rate=max_rate, time_period=time_period)
    logger.info("Set global rate limit to %.1f req/%.1fs", max_rate, time_period)


class RateLimitedModel(Model):
    """Wraps a pydantic-ai Model to enforce global rate limits using aiolimiter."""

    def __init__(self, wrapped_model: Model, limiter: AsyncLimiter | None = None) -> None:
        self.wrapped_model = wrapped_model
        self.limiter = limiter or _global_limiter

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        """Make a rate-limited request using async context manager."""
        async with self.limiter:
            return await self.wrapped_model.request(messages, model_settings, model_request_parameters)

    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[ModelResponse]:
        """Make a rate-limited stream request using async context manager."""
        async with self.limiter:
            async with self.wrapped_model.request_stream(
                messages, model_settings, model_request_parameters
            ) as stream:
                yield stream

    @property
    def model_name(self) -> str:
        return self.wrapped_model.model_name

    @property
    def system(self) -> str | None:
        return self.wrapped_model.system
