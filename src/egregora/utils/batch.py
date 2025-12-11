"""Synchronous helpers for Gemini-style batch operations (HTTP-only stubs)."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

import httpx
from google.genai import types as genai_types
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_core import ValidationError
from tenacity import (
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Shared retry configuration - use tenacity directly with these constants
RETRYABLE_EXCEPTIONS = (UnexpectedModelBehavior, httpx.HTTPError, ValidationError)
RETRY_STOP = stop_after_attempt(5)
RETRY_WAIT = wait_random_exponential(min=2.0, max=60.0)
RETRY_IF = retry_if_exception_type(RETRYABLE_EXCEPTIONS)


def _log_before_retry(retry_state: RetryCallState) -> None:
    """Log before retrying a call."""
    logger.warning(
        "Retrying %s (attempt %d, waiting %.1fs)...",
        retry_state.fn.__name__,
        retry_state.attempt_number,
        retry_state.next_action.sleep,
    )


def sleep_with_progress_sync(duration: float, message: str = "Sleeping") -> None:
    """Sleep for a given duration with a simple loop (no progress bar dependency)."""
    if duration <= 0:
        return
    sleep_interval = 0.1
    slept_time = 0.0
    while slept_time < duration:
        sleep_amount = min(sleep_interval, duration - slept_time)
        time.sleep(sleep_amount)
        slept_time += sleep_amount


@dataclass(slots=True)
class BatchPromptRequest:
    """Single request to be executed in a batch generate job."""

    contents: list[genai_types.Content]
    config: dict | genai_types.GenerateContentConfig | None = None
    model: str | None = None
    tag: str | None = None


@dataclass(slots=True)
class BatchPromptResult:
    """Result of a batch generate job for a single request."""

    tag: str | None
    response: genai_types.GenerateContentResponse | None
    error: genai_types.JobError | None = None


@dataclass(slots=True)
class EmbeddingBatchRequest:
    """Embed request executed through the batch embeddings API."""

    text: str
    tag: str | None = None
    model: str | None = None
    task_type: str | None = None


@dataclass(slots=True)
class EmbeddingBatchResult:
    """Embeddings returned for a single request."""

    tag: str | None
    embedding: list[float] | None
    error: genai_types.JobError | None = None


def _raise_no_embedding() -> None:
    msg = "No embedding returned"
    raise UnexpectedModelBehavior(msg)


class GeminiBatchClient:
    """Synchronous Gemini batch helper built on the official google-genai client."""

    def __init__(
        self,
        client: object,
        default_model: str,
        poll_interval: float = 5.0,
        timeout: float | None = 900.0,
    ) -> None:
        self._client = client
        self._default_model = default_model
        self._poll_interval = poll_interval
        self._timeout = timeout

    @property
    def default_model(self) -> str:
        """Return the default generative model for this batch client."""
        return self._default_model

    def upload_file(self, *, path: str, _display_name: str | None = None) -> genai_types.File:
        display_name = _display_name or path
        return self._client.files.upload(file=path, display_name=display_name)

    def generate_content(
        self,
        requests: Sequence[BatchPromptRequest],
        *,
        _display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[BatchPromptResult]:
        if not requests:
            return []

        poll_seconds = poll_interval or self._poll_interval
        timeout_seconds = timeout or self._timeout

        results: list[BatchPromptResult] = []
        for req in requests:
            model = req.model or self._default_model
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=req.contents,
                    config=req.config or {},
                    timeout=timeout_seconds,
                )
                results.append(BatchPromptResult(tag=req.tag, response=response, error=None))
            except Exception as exc:  # pragma: no cover - exercised in integration
                logger.exception("Batch generate_content failed for tag %s", req.tag)
                results.append(
                    BatchPromptResult(
                        tag=req.tag,
                        response=None,
                        error=genai_types.JobError(code=type(exc).__name__, message=str(exc)),
                    )
                )

            if poll_seconds:
                sleep_with_progress_sync(poll_seconds)

        return results

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        _display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[EmbeddingBatchResult]:
        if not requests:
            return []

        poll_seconds = poll_interval or self._poll_interval
        timeout_seconds = timeout or self._timeout

        results: list[EmbeddingBatchResult] = []
        for req in requests:
            model = req.model or self._default_model
            try:
                if hasattr(self._client, "models") and hasattr(self._client.models, "embed_content"):
                    resp = self._client.models.embed_content(
                        model=model,
                        content=req.text,
                        task_type=req.task_type,
                        timeout=timeout_seconds,
                    )
                    embedding = getattr(resp, "embedding", None)
                    values = getattr(embedding, "values", None) if embedding else None
                else:
                    values = None

                if values is None:
                    _raise_no_embedding()

                results.append(EmbeddingBatchResult(tag=req.tag, embedding=list(values), error=None))
            except Exception as exc:  # pragma: no cover - exercised in integration
                logger.exception("Batch embed_content failed for tag %s", req.tag)
                results.append(
                    EmbeddingBatchResult(
                        tag=req.tag,
                        embedding=None,
                        error=genai_types.JobError(code=type(exc).__name__, message=str(exc)),
                    )
                )

            if poll_seconds:
                sleep_with_progress_sync(poll_seconds)

        return results
