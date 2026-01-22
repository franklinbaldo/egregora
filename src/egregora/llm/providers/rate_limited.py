"""Rate limited model wrapper for pydantic-ai models."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings

from egregora.llm.rate_limit import get_rate_limiter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai.messages import ModelMessage, ModelResponse

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

        # Use async acquire directly, no thread needed
        await limiter.acquire()
        try:
            return await self.wrapped_model.request(messages, model_settings, model_request_parameters)
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

        # Use async acquire directly, no thread needed
        await limiter.acquire()
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
