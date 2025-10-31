"""Intelligent dispatchers for Gemini API calls (embeddings and content generation).

This module provides specialized dispatchers that automatically choose between
batch API operations and parallel individual calls based on request volume.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from google import genai
from google.genai import types as genai_types

from egregora.utils.base_dispatcher import BaseDispatcher
from egregora.utils.batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
    GeminiBatchClient,
)
from egregora.utils.genai import call_with_retries_sync

logger = logging.getLogger(__name__)


class GeminiEmbeddingDispatcher(BaseDispatcher[EmbeddingBatchRequest, EmbeddingBatchResult]):
    """Dispatcher for embedding operations."""

    def __init__(
        self,
        client: genai.Client,
        default_model: str,
        batch_threshold: int = 10,
        max_parallel: int = 5,
    ):
        """Initialize embedding dispatcher.

        Args:
            client: Gemini client instance
            default_model: Default embedding model to use
            batch_threshold: Minimum requests for batch API
            max_parallel: Maximum parallel workers
        """
        super().__init__(batch_threshold, max_parallel)
        self._client = client
        self._batch_client = GeminiBatchClient(client, default_model)
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        """Return the default embedding model."""
        return self._default_model

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[EmbeddingBatchResult]:
        """Embed content using optimal strategy (batch or individual).

        Args:
            requests: Embedding requests to execute
            force_batch: Force batch API
            force_individual: Force individual calls
            display_name: Display name for batch job
            poll_interval: Polling interval for batch job
            timeout: Timeout for batch job

        Returns:
            List of embedding results
        """
        return self.dispatch(
            requests,
            force_batch=force_batch,
            force_individual=force_individual,
            display_name=display_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def _execute_one(self, request: EmbeddingBatchRequest) -> EmbeddingBatchResult:
        """Execute a single embedding request via direct API."""
        try:
            # Build config for task_type and output_dimensionality
            config = None
            if request.task_type or request.output_dimensionality:
                config = genai_types.EmbedContentConfig(
                    task_type=request.task_type,
                    output_dimensionality=request.output_dimensionality,
                )

            response = call_with_retries_sync(
                self._client.models.embed_content,
                model=request.model or self._default_model,
                contents=request.text,
                config=config,
            )

            # Extract embedding from response object
            embedding = getattr(response, "embedding", None)
            values = getattr(embedding, "values", None)
            if values:
                return EmbeddingBatchResult(tag=request.tag, embedding=list(values))
            return EmbeddingBatchResult(tag=request.tag, embedding=None)

        except Exception as e:
            logger.warning(
                f"Individual embedding failed for tag={request.tag}: {e}",
                exc_info=True,
            )
            return EmbeddingBatchResult(tag=request.tag, embedding=None, error=e)

    def _execute_batch(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        **kwargs,
    ) -> list[EmbeddingBatchResult]:
        """Execute embeddings via batch API."""
        return self._batch_client.embed_content(
            requests,
            display_name=kwargs.get("display_name"),
            poll_interval=kwargs.get("poll_interval"),
            timeout=kwargs.get("timeout"),
        )


class GeminiGenerationDispatcher(BaseDispatcher[BatchPromptRequest, BatchPromptResult]):
    """Dispatcher for content generation operations."""

    def __init__(
        self,
        client: genai.Client,
        default_model: str,
        batch_threshold: int = 10,
        max_parallel: int = 5,
    ):
        """Initialize generation dispatcher.

        Args:
            client: Gemini client instance
            default_model: Default generation model to use
            batch_threshold: Minimum requests for batch API
            max_parallel: Maximum parallel workers
        """
        super().__init__(batch_threshold, max_parallel)
        self._client = client
        self._batch_client = GeminiBatchClient(client, default_model)
        self._default_model = default_model

    @property
    def default_model(self) -> str:
        """Return the default generation model."""
        return self._default_model

    def generate_content(
        self,
        requests: Sequence[BatchPromptRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[BatchPromptResult]:
        """Generate content using optimal strategy (batch or individual).

        Args:
            requests: Generation requests to execute
            force_batch: Force batch API
            force_individual: Force individual calls
            display_name: Display name for batch job
            poll_interval: Polling interval for batch job
            timeout: Timeout for batch job

        Returns:
            List of generation results
        """
        return self.dispatch(
            requests,
            force_batch=force_batch,
            force_individual=force_individual,
            display_name=display_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def _execute_one(self, request: BatchPromptRequest) -> BatchPromptResult:
        """Execute a single generation request via direct API."""
        try:
            response = call_with_retries_sync(
                self._client.models.generate_content,
                model=request.model or self._default_model,
                contents=request.contents,
                config=request.config,
            )
            return BatchPromptResult(tag=request.tag, response=response, error=None)

        except Exception as e:
            logger.warning(
                f"Individual generation failed for tag={request.tag}: {e}",
                exc_info=True,
            )
            return BatchPromptResult(tag=request.tag, response=None, error=e)

    def _execute_batch(
        self,
        requests: Sequence[BatchPromptRequest],
        **kwargs,
    ) -> list[BatchPromptResult]:
        """Execute generation via batch API."""
        return self._batch_client.generate_content(
            requests,
            display_name=kwargs.get("display_name"),
            poll_interval=kwargs.get("poll_interval"),
            timeout=kwargs.get("timeout"),
        )


class GeminiDispatcher:
    """Unified dispatcher providing both embedding and generation capabilities.

    This class maintains backward compatibility with the old SmartGeminiClient
    by providing both embed_content() and generate_content() methods.

    Internally, it delegates to specialized dispatchers for each operation type.
    """

    def __init__(
        self,
        client: genai.Client,
        default_model: str,
        batch_threshold: int = 10,
        max_parallel: int = 5,
    ):
        """Initialize unified dispatcher.

        Args:
            client: Gemini client instance
            default_model: Default model (used for both embedding and generation)
            batch_threshold: Minimum requests for batch API
            max_parallel: Maximum parallel workers
        """
        self._client = client
        self._default_model = default_model
        self._batch_threshold = batch_threshold
        self._max_parallel = max_parallel

        # Create specialized dispatchers
        self._embedding_dispatcher = GeminiEmbeddingDispatcher(
            client, default_model, batch_threshold, max_parallel
        )
        self._generation_dispatcher = GeminiGenerationDispatcher(
            client, default_model, batch_threshold, max_parallel
        )

        # Expose batch client for direct access (compatibility)
        self._batch_client = self._generation_dispatcher._batch_client

    @property
    def default_model(self) -> str:
        """Return the default model."""
        return self._default_model

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[EmbeddingBatchResult]:
        """Embed content - delegates to embedding dispatcher."""
        return self._embedding_dispatcher.embed_content(
            requests,
            force_batch=force_batch,
            force_individual=force_individual,
            display_name=display_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def generate_content(
        self,
        requests: Sequence[BatchPromptRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
        display_name: str | None = None,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> list[BatchPromptResult]:
        """Generate content - delegates to generation dispatcher."""
        return self._generation_dispatcher.generate_content(
            requests,
            force_batch=force_batch,
            force_individual=force_individual,
            display_name=display_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    def upload_file(self, *, path: str, display_name: str | None = None) -> genai_types.File:
        """Upload a media file (uses direct API, no batching).

        File uploads are fast and don't benefit from batching, so they always
        use the direct API through the batch client.
        """
        return self._batch_client.upload_file(path=path, display_name=display_name)


# Backward compatibility alias
SmartGeminiClient = GeminiDispatcher
