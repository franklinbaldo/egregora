from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from google import genai

from egregora.utils.batch import (
    BatchPromptRequest,
    BatchPromptResult,
    EmbeddingBatchRequest,
    EmbeddingBatchResult,
    GeminiBatchClient,
)
from egregora.utils.genai import call_with_retries_sync

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SmartGeminiClient:
    """Intelligent client that chooses between batch and individual calls."""

    def __init__(
        self,
        client: genai.Client,
        default_model: str,
        batch_threshold: int = 10,
        max_parallel: int = 5,
    ):
        self._client = client
        self._batch_client = GeminiBatchClient(client, default_model)
        self._batch_threshold = batch_threshold
        self._max_parallel = max_parallel
        self._default_model = default_model

    def embed_content(
        self,
        requests: Sequence[EmbeddingBatchRequest],
        *,
        force_batch: bool = False,
        force_individual: bool = False,
    ) -> list[EmbeddingBatchResult]:
        """Smart embedding with automatic strategy selection."""
        if not requests:
            return []

        if force_batch and force_individual:
            raise ValueError("Cannot force both batch and individual strategies")

        # Allow manual override
        if force_batch:
            return self._embed_batch(requests)
        if force_individual:
            return self._embed_individual(requests)

        # Automatic decision
        if len(requests) < self._batch_threshold:
            logger.info(f"Using individual calls for {len(requests)} items")
            return self._embed_individual(requests)
        else:
            logger.info(f"Using batch API for {len(requests)} items")
            return self._embed_batch(requests)

    def _embed_individual(
        self, requests: Sequence[EmbeddingBatchRequest]
    ) -> list[EmbeddingBatchResult]:
        """Execute requests individually with parallelism."""
        with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
            futures = [executor.submit(self._embed_one, req) for req in requests]
            return [f.result() for f in futures]

    def _embed_one(self, request: EmbeddingBatchRequest) -> EmbeddingBatchResult:
        """Single embedding via direct API."""
        try:
            response = call_with_retries_sync(
                self._client.embed_content,
                model=request.model or self._default_model,
                content=request.text,
                task_type=request.task_type,
                output_dimensionality=request.output_dimensionality,
            )
            return EmbeddingBatchResult(
                tag=request.tag, embedding=list(response["embedding"])
            )
        except Exception as e:
            logger.warning(
                f"Individual embedding failed for tag={request.tag}: {e}",
                exc_info=True,
            )
            # Match the batch client's error handling by returning a result with an error
            return EmbeddingBatchResult(tag=request.tag, embedding=None, error=e)

    def _embed_batch(
        self, requests: Sequence[EmbeddingBatchRequest]
    ) -> list[EmbeddingBatchResult]:
        """Use batch API."""
        return self._batch_client.embed_content(requests)

    @property
    def default_model(self) -> str:
        """Returns the default model name."""
        return self._default_model

    def upload_file(self, path: str, display_name: str | None = None) -> genai.File:
        """Uploads a file to the underlying client."""
        return self._client.upload_file(path, display_name=display_name)

    def generate_content(self, requests, *, force_batch: bool = False, force_individual: bool = False):
        """Smart content generation with automatic strategy selection."""
        if not requests:
            return []

        if force_batch and force_individual:
            raise ValueError("Cannot force both batch and individual strategies")

        # Allow manual override
        if force_batch:
            return self._generate_batch(requests)
        if force_individual:
            return self._generate_individual(requests)

        # Automatic decision
        if len(requests) < self._batch_threshold:
            logger.info(f"Using individual calls for {len(requests)} items")
            return self._generate_individual(requests)
        else:
            logger.info(f"Using batch API for {len(requests)} items")
            return self._generate_batch(requests)

    def _generate_individual(self, requests):
        """Execute requests individually with parallelism."""
        with ThreadPoolExecutor(max_workers=self._max_parallel) as executor:
            futures = [executor.submit(self._generate_one, req) for req in requests]
            return [f.result() for f in futures]

    def _generate_one(self, request: "BatchPromptRequest"):
        """Single generation via direct API."""
        try:
            response = call_with_retries_sync(
                self._client.generate_content,
                model=request.model or self._default_model,
                contents=request.contents,
                generation_config=request.config,
            )
            return BatchPromptResult(tag=request.tag, response=response)
        except Exception as e:
            logger.warning(
                f"Individual generation failed for tag={request.tag}: {e}",
                exc_info=True,
            )
            # Match the batch client's error handling by returning a result with an error
            return BatchPromptResult(tag=request.tag, response=None, error=e)

    def _generate_batch(self, requests: Sequence["BatchPromptRequest"]):
        """Use batch API."""
        return self._batch_client.generate_content(requests)