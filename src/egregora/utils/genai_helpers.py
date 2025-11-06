"""Simple helpers for embeddings and content generation using google.genai client.

This module provides straightforward functions for embeddings and content generation
without the batch API complexity. All operations use the direct genai client with
retry logic for rate limiting.
"""

from __future__ import annotations

import logging
from typing import Annotated

from google import genai
from google.genai import types as genai_types

from egregora.utils.genai import call_with_retries_sync

logger = logging.getLogger(__name__)


def embed_text(
    client: Annotated[genai.Client, "The Gemini API client"],
    text: Annotated[str, "The text to embed"],
    *,
    model: Annotated[str, "The embedding model to use"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    output_dimensionality: Annotated[int | None, "The output dimensionality"] = None,
) -> Annotated[list[float], "The embedding vector"]:
    """Embed a single text using the genai client.

    Args:
        client: Gemini API client
        text: Text to embed
        model: Embedding model name (e.g., "models/text-embedding-004")
        task_type: Optional task type (e.g., "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY")
        output_dimensionality: Optional output dimensionality (e.g., 768, 3072)

    Returns:
        List of floats representing the embedding vector

    Raises:
        RuntimeError: If embedding fails
    """
    # Build config if needed
    config = None
    if task_type or output_dimensionality:
        config = genai_types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )

    try:
        response = call_with_retries_sync(
            client.models.embed_content,
            model=model,
            contents=text,
            config=config,
        )

        # Extract embedding from response
        embedding = getattr(response, "embedding", None)
        values = getattr(embedding, "values", None) if embedding else None

        if values is None:
            raise RuntimeError(f"No embedding returned for text: {text[:50]}...")

        return list(values)

    except Exception as e:
        logger.error("Failed to embed text: %s", e, exc_info=True)
        raise RuntimeError(f"Embedding failed: {e}") from e


def embed_batch(
    client: Annotated[genai.Client, "The Gemini API client"],
    texts: Annotated[list[str], "List of texts to embed"],
    *,
    model: Annotated[str, "The embedding model to use"],
    task_type: Annotated[str | None, "The task type for the embedding"] = None,
    output_dimensionality: Annotated[int | None, "The output dimensionality"] = None,
) -> Annotated[list[list[float]], "List of embedding vectors"]:
    """Embed multiple texts using individual API calls.

    This replaces batch API calls with sequential individual calls.
    Each call includes retry logic for rate limiting.

    Args:
        client: Gemini API client
        texts: List of texts to embed
        model: Embedding model name
        task_type: Optional task type
        output_dimensionality: Optional output dimensionality

    Returns:
        List of embedding vectors

    Raises:
        RuntimeError: If any embedding fails
    """
    if not texts:
        return []

    logger.info("[blue]📚 Embedding model:[/] %s — %d text(s)", model, len(texts))

    embeddings: list[list[float]] = []
    for i, text in enumerate(texts):
        try:
            embedding = embed_text(
                client,
                text,
                model=model,
                task_type=task_type,
                output_dimensionality=output_dimensionality,
            )
            embeddings.append(embedding)
        except Exception as e:
            logger.error("Failed to embed text %d/%d: %s", i + 1, len(texts), e)
            raise

    logger.info("Embedded %d text(s)", len(embeddings))
    return embeddings


def generate_content(
    client: Annotated[genai.Client, "The Gemini API client"],
    contents: Annotated[list[genai_types.Content], "The contents to generate from"],
    *,
    model: Annotated[str, "The generation model to use"],
    config: Annotated[genai_types.GenerateContentConfig | None, "Optional generation config"] = None,
) -> Annotated[genai_types.GenerateContentResponse, "The generated response"]:
    """Generate content using the genai client.

    Args:
        client: Gemini API client
        contents: List of Content objects (messages)
        model: Generation model name
        config: Optional generation configuration

    Returns:
        Generated content response

    Raises:
        RuntimeError: If generation fails
    """
    try:
        response = call_with_retries_sync(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=config,
        )
        return response

    except Exception as e:
        logger.error("Failed to generate content: %s", e, exc_info=True)
        raise RuntimeError(f"Content generation failed: {e}") from e


def upload_file(
    client: Annotated[genai.Client, "The Gemini API client"],
    *,
    path: Annotated[str, "Path to the file to upload"],
) -> Annotated[genai_types.File, "The uploaded file object"]:
    """Upload a media file and wait for it to become ACTIVE.

    Args:
        client: Gemini API client
        path: Path to the file to upload

    Returns:
        Uploaded file object

    Raises:
        RuntimeError: If upload or activation fails
    """
    import time

    logger.debug("Uploading media file: %s", path)

    try:
        uploaded_file = call_with_retries_sync(client.files.upload, file=path)

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
            uploaded_file = call_with_retries_sync(client.files.get, name=uploaded_file.name)
            logger.debug(
                "Waiting for file %s to become ACTIVE (current: %s, elapsed: %ds)",
                path,
                uploaded_file.state.name,
                elapsed,
            )

        return uploaded_file

    except Exception as e:
        logger.error("Failed to upload file %s: %s", path, e, exc_info=True)
        raise RuntimeError(f"File upload failed: {e}") from e


def generate_content_batch(
    client: Annotated[genai.Client, "The Gemini API client"],
    requests: Annotated[list, "List of BatchPromptRequest objects"],
    *,
    default_model: Annotated[str, "Default model to use if not specified in request"],
) -> Annotated[list, "List of BatchPromptResult objects"]:
    """Generate content for multiple requests using individual API calls.

    This function replaces GeminiBatchClient.generate_content() by processing
    BatchPromptRequest objects sequentially.

    Args:
        client: Gemini API client
        requests: List of BatchPromptRequest objects (from egregora.utils.batch)
        default_model: Default model name

    Returns:
        List of BatchPromptResult objects with responses or errors

    Note:
        This imports BatchPromptResult locally to avoid circular dependencies.
    """
    # Import here to avoid circular dependency
    from egregora.utils.batch import BatchPromptResult

    if not requests:
        return []

    logger.info("[blue]🧠 Generation model:[/] %s — %d request(s)", default_model, len(requests))

    results: list[BatchPromptResult] = []

    for req in requests:
        model = req.model or default_model
        try:
            response = call_with_retries_sync(
                client.models.generate_content,
                model=model,
                contents=req.contents,
                config=req.config,
            )
            results.append(BatchPromptResult(tag=req.tag, response=response, error=None))

        except Exception as e:
            logger.warning(
                "Generation failed for tag=%s: %s",
                req.tag,
                str(e),
            )
            results.append(BatchPromptResult(tag=req.tag, response=None, error=e))

    return results
