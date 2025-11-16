"""Configure Pydantic-AI HTTP clients to use Tenacity-backed retries."""

from __future__ import annotations

from functools import wraps

from httpx import AsyncClient, HTTPStatusError
from pydantic_ai import models as pyd_models
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

RETRY_CONFIG = RetryConfig(
    retry=retry_if_exception_type(HTTPStatusError),
    wait=wait_retry_after(max_wait=300),
    stop=stop_after_attempt(5),
    reraise=True,
)


def _attach_tenacity(client: AsyncClient) -> AsyncClient:
    """Wrap the client's transport once so we honor Retry-After headers."""
    transport = getattr(client, "_transport", None)
    if isinstance(transport, AsyncTenacityTransport):
        return client

    tenacity_transport = AsyncTenacityTransport(
        config=RETRY_CONFIG,
        wrapped=transport,
        validate_response=lambda response: response.raise_for_status(),
    )
    client._transport = tenacity_transport
    return client


def install_pydantic_ai_retry_transport() -> None:
    """Patch ``cached_async_http_client`` to return Tenacity-wrapped HTTPX clients."""
    if getattr(pyd_models.cached_async_http_client, "__egregora_tenacity__", False):
        return

    original = pyd_models.cached_async_http_client

    @wraps(original)
    def wrapped(*, provider: str | None = None, timeout: int = 600, connect: int = 5) -> AsyncClient:
        client = original(provider=provider, timeout=timeout, connect=connect)
        return _attach_tenacity(client)

    wrapped.__egregora_tenacity__ = True
    pyd_models.cached_async_http_client = wrapped
