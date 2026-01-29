"""Rate limited model wrapper for pydantic-ai models."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings

from egregora.llm.rate_limit import get_rate_limiter

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pydantic_ai import RunContext
    from pydantic_ai.messages import ModelMessage, ModelResponse
    from pydantic_ai.models import StreamedResponse

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
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        """Make a rate-limited stream request."""
        limiter = get_rate_limiter()

        # Use async acquire directly, no thread needed
        await limiter.acquire()
        try:
            # Note: passing run_context might fail if wrapped_model doesn't support it in older versions
            # but we are fixing type signature to match base class.
            kwargs = {}
            if run_context is not None:
                kwargs["run_context"] = run_context

            async with self.wrapped_model.request_stream(
                messages, model_settings, model_request_parameters, **kwargs
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
