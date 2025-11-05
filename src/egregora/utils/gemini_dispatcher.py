"""Intelligent dispatchers for Gemini API calls (embeddings and content generation).

This module provides specialized dispatchers that automatically choose between
batch API operations and parallel individual calls based on request volume.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Annotated

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
        client: Annotated[genai.Client, "The Gemini API client"],
        default_model: Annotated[str, "The default embedding model to use"],
        batch_threshold: Annotated[int, "The batch size threshold"] = 10,
        max_parallel: Annotated[int, "The maximum number of parallel workers"] = 5,
    ) -> None:
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
        requests: Annotated[Sequence[EmbeddingBatchRequest], "A sequence of embedding requests"],
        **kwargs,
    ) -> Annotated[list[EmbeddingBatchResult], "A list of embedding results"]:
        """Embed content using optimal strategy (batch or individual).
        Args:
            requests: Embedding requests to execute
            **kwargs: Additional arguments for dispatching, including `force_batch`,
                `force_individual`, `display_name`, `poll_interval`, and `timeout`.
        Returns:
            List of embedding results
        """
        return self.dispatch(requests, **kwargs)

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
            values = getattr(embedding, "values", None) if embedding else None
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
        client: Annotated[genai.Client, "The Gemini API client"],
        default_model: Annotated[str, "The default generation model to use"],
        batch_threshold: Annotated[int, "The batch size threshold"] = 10,
        max_parallel: Annotated[int, "The maximum number of parallel workers"] = 5,
    ) -> None:
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
        requests: Annotated[Sequence[BatchPromptRequest], "A sequence of prompt requests"],
        **kwargs,
    ) -> Annotated[list[BatchPromptResult], "A list of prompt results"]:
        """Generate content using optimal strategy (batch or individual).
        Args:
            requests: Generation requests to execute
            **kwargs: Additional arguments for dispatching, including `force_batch`,
                `force_individual`, `display_name`, `poll_interval`, and `timeout`.
        Returns:
            List of generation results
        """
        return self.dispatch(requests, **kwargs)

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
        client: Annotated[genai.Client, "The Gemini API client"],
        default_model: Annotated[str, "The default model to use for both embedding and generation"],
        batch_threshold: Annotated[int, "The batch size threshold"] = 10,
        max_parallel: Annotated[int, "The maximum number of parallel workers"] = 5,
    ) -> None:
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
        requests: Annotated[Sequence[EmbeddingBatchRequest], "A sequence of embedding requests"],
        **kwargs,
    ) -> Annotated[list[EmbeddingBatchResult], "A list of embedding results"]:
        """Embed content - delegates to embedding dispatcher."""
        return self._embedding_dispatcher.embed_content(requests, **kwargs)

    def generate_content(
        self,
        requests: Annotated[Sequence[BatchPromptRequest], "A sequence of prompt requests"],
        **kwargs,
    ) -> Annotated[list[BatchPromptResult], "A list of prompt results"]:
        """Generate content - delegates to generation dispatcher."""
        return self._generation_dispatcher.generate_content(requests, **kwargs)

    def upload_file(
        self,
        *,
        path: Annotated[str, "The path to the file to upload"],
        display_name: Annotated[str | None, "An optional display name for the file"] = None,
    ) -> Annotated[genai_types.File, "The uploaded file object"]:
        """Upload a media file (uses direct API, no batching).

        File uploads are fast and don't benefit from batching, so they always
        use the direct API through the batch client.
        """
        return self._batch_client.upload_file(path=path, display_name=display_name)


# Backward compatibility alias
SmartGeminiClient = GeminiDispatcher
