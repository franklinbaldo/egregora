"""Synchronous helpers for running Gemini Batch API jobs."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from google.api_core import exceptions as google_exceptions
from google.genai import types as genai_types
from tenacity import RetryCallState, retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type
from tqdm import tqdm

from egregora.config import EMBEDDING_DIM

# utils/genai.py was removed; logic should be migrated or referenced from correct location
# Assuming simple sleep/retry are acceptable replacements here, or they should be in utils

T = TypeVar("T")

logger = logging.getLogger(__name__)


# New retry implementation using tenacity
_RETRYABLE_ERRORS = (
    google_exceptions.ResourceExhausted,
    google_exceptions.ServiceUnavailable,
    google_exceptions.InternalServerError,
    google_exceptions.GatewayTimeout,
)
_MAX_RETRIES = 5
_INITIAL_WAIT_SECONDS = 2.0
_MAX_WAIT_SECONDS = 60.0


def _log_before_retry(retry_state: "RetryCallState") -> None:
    """Log before retrying a call."""
    logger.warning(
        "Retrying %s (attempt %d, waiting %.1fs)...",
        retry_state.fn.__name__,
        retry_state.attempt_number,
        retry_state.next_action.sleep,
    )

@retry(
    stop=stop_after_attempt(_MAX_RETRIES),
    wait=wait_random_exponential(min=_INITIAL_WAIT_SECONDS, max=_MAX_WAIT_SECONDS),
    before_sleep=_log_before_retry,
    retry=retry_if_exception_type(_RETRYABLE_ERRORS),
)
def call_with_retries_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Execute a synchronous function with exponential backoff and jitter.
    Args:
        func: The function to execute.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.
    Returns:
        The result of the function.
    Raises:
        Exception: If the function fails after all retry attempts.
    """
    return func(*args, **kwargs)


def sleep_with_progress_sync(duration: float, message: str = "Sleeping") -> None:
    """Sleep for a given duration with a progress bar.
    Args:
        duration: The number of seconds to sleep.
        message: The message to display in the progress bar.
    """
    if duration <= 0:
        return

    # Use a small sleep interval to update the progress bar smoothly
    sleep_interval = 0.1
    with tqdm(total=duration, desc=message, unit="s", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:
        slept_time = 0
        while slept_time < duration:
            sleep_amount = min(sleep_interval, duration - slept_time)
            time.sleep(sleep_amount)
            pbar.update(sleep_amount)
            slept_time += sleep_amount


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from google import genai




@dataclass(slots=True)
class BatchPromptRequest:
    """Single request to be executed in a batch generate job."""

    contents: list[genai_types.Content]
    config: genai_types.GenerateContentConfig | None = None
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
    """Embed request executed through the batch embeddings API.

    All embeddings use fixed 768-dimension output.
    """

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




class GeminiBatchClient:
    """Minimal synchronous wrapper around ``client.batches``.
    Args:
        client: The Google GenAI client.
        default_model: The default model to use for batch jobs.
        poll_interval: The default polling interval in seconds.
        timeout: The default timeout in seconds.
    """

    def __init__(
        self,
        client: "genai.Client",
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
        """Upload a media file and wait for it to become ACTIVE before returning."""
        logger.debug("Uploading media for batch processing: %s", path)
        # Newer google-genai clients accept only the file path/handle; display
        # names are deprecated, so we ignore them here for compatibility.
        uploaded_file = call_with_retries_sync(self._client.files.upload, file=path)

        # Wait for file to become ACTIVE (required before use)
        max_wait = 60  # seconds
        poll_interval = 2  # seconds
        elapsed = 0
        while uploaded_file.state.name != "ACTIVE":
            if elapsed >= max_wait:
                logger.warning(
                    "File %s did not become ACTIVE after %ds (state: %s)",
                    path,
                    max_wait,
                    uploaded_file.state.name,
                )
                break
            time.sleep(poll_interval)
            elapsed += poll_interval
            uploaded_file = call_with_retries_sync(self._client.files.get, name=uploaded_file.name)
            logger.debug(
                "Waiting for file %s to become ACTIVE (current: %s, elapsed: %ds)",
                path,
                uploaded_file.state.name,
                elapsed,
            )

        return uploaded_file

    def generate_content(
        self,
        requests: Sequence[BatchPromptRequest],
        *,
        _display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[BatchPromptResult]:
        """Execute a batch generate job and return responses in order.
        Args:
            requests: A sequence of batch prompt requests.
            _display_name: A display name for the batch job.
            poll_interval: The polling interval in seconds.
            timeout: The timeout in seconds.
        Returns:
            A list of batch prompt results.
        """
        if not requests:
            return []

        inlined_requests = [
            genai_types.InlinedRequest(
                model=req.model or self._default_model,
                contents=req.contents,
                config=req.config,
            )
            for req in requests
        ]

        logger.info(
            "[blue]🧠 Batch model:[/] %s — %d request(s)",
            self._default_model,
            len(inlined_requests),
        )

        job = call_with_retries_sync(
            self._client.batches.create,
            model=self._default_model,
            src=genai_types.BatchJobSource(inlined_requests=inlined_requests),
        )

        logger.info("[cyan]🚀 Batch job created:[/] %s", job.name or "<unknown>")
        completed_job = self._poll_until_done(
            job.name,
            interval=poll_interval,
            timeout=timeout,
        )

        responses = (completed_job.dest.inlined_responses if completed_job.dest else None) or []

        results: list[BatchPromptResult] = []

        for index, request in enumerate(requests):
            response_obj = responses[index] if index < len(responses) else None
            response = getattr(response_obj, "response", None) if response_obj else None
            error = getattr(response_obj, "error", None) if response_obj else None

            if error:
                logger.warning(
                    "[yellow]⚠️ Batch item failed[/] tag=%s index=%d code=%s message=%s",
                    request.tag,
                    index,
                    getattr(error, "code", "n/a"),
                    getattr(error, "message", "unknown error"),
                )

            results.append(
                BatchPromptResult(
                    tag=request.tag,
                    response=response,
                    error=error,
                )
            )

        return results

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        _display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[EmbeddingBatchResult]:
        """Execute a batch embedding job.
        Args:
            requests: A sequence of embedding batch requests.
            _display_name: A display name for the batch job.
            poll_interval: The polling interval in seconds.
            timeout: The timeout in seconds.
        Returns:
            A list of embedding batch results.
        """
        if not requests:
            return []

        model_name = next((req.model for req in requests if req.model), self._default_model)

        task_type = next((req.task_type for req in requests if req.task_type), None)
        if any(req.task_type not in (None, task_type) for req in requests):
            msg = "All embedding batch requests must use the same task_type"
            raise ValueError(msg)

        # Always use fixed 768 dimensions for all embeddings
        embed_config = genai_types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=EMBEDDING_DIM,
        )

        contents = [genai_types.Content(parts=[genai_types.Part(text=req.text)]) for req in requests]

        source = genai_types.EmbeddingsBatchJobSource(
            inlined_requests=genai_types.EmbedContentBatch(
                contents=contents,
                config=embed_config,
            )
        )

        logger.info("[blue]📚 Embedding model:[/] %s — %d item(s)", model_name, len(contents))

        job = call_with_retries_sync(
            self._client.batches.create_embeddings,
            model=model_name,
            src=source,
        )

        logger.info("[cyan]🚀 Embedding job created:[/] %s", job.name or "<unknown>")
        completed_job = self._poll_until_done(
            job.name,
            interval=poll_interval,
            timeout=timeout,
        )

        responses = (completed_job.dest.inlined_embed_content_responses if completed_job.dest else None) or []

        results: list[EmbeddingBatchResult] = []
        for index, req in enumerate(requests):
            response_obj = responses[index] if index < len(responses) else None
            response = getattr(response_obj, "response", None) if response_obj else None
            error = getattr(response_obj, "error", None) if response_obj else None

            embedding_values: list[float] | None = None
            if response and response.embedding:
                embedding_values = list(response.embedding.values)

            if error:
                logger.warning(
                    "[yellow]⚠️ Embed item failed[/] tag=%s index=%d code=%s message=%s",
                    req.tag,
                    index,
                    getattr(error, "code", "n/a"),
                    getattr(error, "message", "unknown error"),
                )

            results.append(
                EmbeddingBatchResult(
                    tag=req.tag,
                    embedding=embedding_values,
                    error=error,
                )
            )

        return results

    def _poll_until_done(
        self,
        job_name: str,
        *,
        interval: float | None,
        timeout: float | None,
    ) -> genai_types.BatchJob:
        """Poll the batch job until it reaches a terminal state."""
        poll_interval = interval or self._poll_interval
        max_timeout = timeout or self._timeout
        start = time.monotonic()
        last_state = None

        while True:
            job = call_with_retries_sync(self._client.batches.get, name=job_name)
            state = job.state.name if job.state else "JOB_STATE_UNSPECIFIED"

            if state != last_state:
                logger.info("[cyan]📡 Batch job %s state:[/] %s", job_name, state.replace("JOB_STATE_", ""))
                last_state = state

            if job.done:
                if state not in {"JOB_STATE_SUCCEEDED", "JOB_STATE_PARTIALLY_SUCCEEDED"}:
                    error_message = (
                        getattr(job.error, "message", "unknown error") if job.error else "unknown error"
                    )
                    msg = f"Batch job {job_name} finished with state {state}: {error_message}"
                    raise RuntimeError(msg)

                elapsed = time.monotonic() - start
                logger.info("[green]✅ Batch job %s completed in %.1fs[/green]", job_name, elapsed)
                return job

            if max_timeout is not None and (time.monotonic() - start) > max_timeout:
                msg = f"Batch job {job_name} exceeded timeout ({max_timeout}s)"
                raise TimeoutError(msg)

            sleep_with_progress_sync(poll_interval, f"Waiting for {job_name}")


def chunk_requests[T](items: Sequence[T], *, size: int) -> Iterable[Sequence[T]]:
    """Yield fixed-size batches from ``items``."""
    if size <= 0:
        msg = "Batch size must be positive"
        raise ValueError(msg)

    for index in range(0, len(items), size):
        yield items[index : index + size]
