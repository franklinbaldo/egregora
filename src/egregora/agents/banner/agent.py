"""Pydantic-AI powered banner generation agent.

This module implements banner generation using a single multimodal model
(gemini-2.0-flash-exp-image) that directly generates images from text prompts.

No separate "creative director" LLM - the image model handles both creative
interpretation and generation in a single API call.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import google.genai as genai
import httpx
from google.api_core import exceptions as google_exceptions
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import Retrying

from egregora.config import EgregoraConfig
from egregora.data_primitives.document import Document, DocumentType
from egregora.resources.prompts import render_prompt
from egregora.utils.retry import RETRY_IF, RETRY_STOP, RETRY_WAIT

if TYPE_CHECKING:
    from collections.abc import Sequence


logger = logging.getLogger(__name__)

_POLL_INTERVAL = 10.0
_TIMEOUT = 600.0  # 10 minutes for batch


@dataclass
class ImageGenerationRequest:
    """Request parameters for generating an image."""

    prompt: str
    response_modalities: Sequence[str]
    aspect_ratio: str | None = None


@dataclass
class ImageGenerationResult:
    """Normalized response from an image generation provider."""

    image_bytes: bytes | None
    mime_type: str | None
    debug_text: str | None = None
    error: str | None = None
    error_code: str | None = None

    @property
    def has_image(self) -> bool:
        """True when binary image data is available."""
        return self.image_bytes is not None and self.mime_type is not None


class BannerInput(BaseModel):
    """Input parameters for banner generation."""

    post_title: str = Field(description="Blog post title")
    post_summary: str = Field(description="Brief summary of the post")
    slug: str | None = Field(default=None, description="Post slug for metadata")
    language: str = Field(default="pt-BR", description="Content language")


class BannerOutput(BaseModel):
    """Output from banner generation.

    Contains a Document with binary image content. Filesystem operations
    (saving, paths, URLs) are handled by upper layers.
    """

    document: Document | None = None
    error: str | None = None
    error_code: str | None = Field(
        default=None,
        description="Optional machine-readable code describing banner failures.",
    )
    debug_text: str | None = Field(
        default=None,
        description="Raw debug output from the image provider, when available.",
    )

    @property
    def success(self) -> bool:
        """True if a document was successfully generated."""
        return self.document is not None


def _build_payload(request: ImageGenerationRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": "banner-req",
        "request": {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generation_config": {},
        },
    }
    if request.response_modalities:
        payload["request"]["generation_config"]["responseModalities"] = list(request.response_modalities)
    return payload


def _write_payload(payload: dict[str, Any]) -> Path:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp_file:
        temp_file.write(json.dumps(payload) + "\n")
        return Path(temp_file.name)


def _upload_payload(client: Any, temp_path: Path) -> types.File:
    return client.files.upload(
        path=temp_path,
        display_name="banner-batch",
        mime_type="application/json",
    )


def _create_batch_job(client: Any, model: str, src: str) -> types.BatchJob:
    job = client.batches.create(
        model=model,
        src=src,
        config=types.CreateBatchJobConfig(display_name="banner-batch-job"),
    )
    logger.info("Created banner batch job: %s", job.name)
    return job


def _wait_for_completion(client: Any, job_name: str) -> types.BatchJob | None:
    start_time = time.time()
    while time.time() - start_time < _TIMEOUT:
        job = client.batches.get(name=job_name)
        if job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED"):
            time.sleep(_POLL_INTERVAL)
            continue
        return job
    return None


def _download_result(output_uri: str) -> dict[str, Any]:
    response = httpx.get(output_uri, timeout=_TIMEOUT)
    response.raise_for_status()
    line = response.text.strip()
    return {"error": "Empty result file"} if not line else json.loads(line)


def _decode_inline_data(inline: dict[str, Any]) -> tuple[bytes | None, str | None]:
    data_field = inline.get("data")
    image_bytes: bytes | None = None
    if isinstance(data_field, str):
        image_bytes = base64.b64decode(data_field)
    elif isinstance(data_field, bytes):
        image_bytes = data_field
    return image_bytes, inline.get("mimeType")


def _extract_image(data: dict[str, Any]) -> ImageGenerationResult:
    if "error" in data:
        return ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            error=str(data["error"]),
            error_code="GENERATION_ERROR",
        )

    candidates = data.get("response", {}).get("candidates", [])
    image_bytes: bytes | None = None
    mime_type: str | None = None
    debug_text_parts: list[str] = []

    for candidate in candidates:
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                debug_text_parts.append(text)
            inline = part.get("inlineData")
            if inline and image_bytes is None:
                image_bytes, mime_type = _decode_inline_data(inline)

    debug_text = "\n".join(debug_text_parts) if debug_text_parts else None

    return (
        ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            debug_text=debug_text,
            error="No image data found in response",
            error_code="NO_IMAGE",
        )
        if image_bytes is None
        else ImageGenerationResult(image_bytes=image_bytes, mime_type=mime_type, debug_text=debug_text)
    )


def _cleanup_temp_file(temp_path: Path) -> None:
    if temp_path.exists():
        temp_path.unlink()


def _build_image_prompt(input_data: BannerInput) -> str:
    return render_prompt(
        "banner.jinja",
        post_title=input_data.post_title,
        post_summary=input_data.post_summary,
    )


def _generate_banner_image(
    client: Any,
    input_data: BannerInput,
    image_model: str,
    generation_request: ImageGenerationRequest,
) -> BannerOutput:
    logger.info("Generating banner with %s for: %s", image_model, input_data.post_title)

    try:
        payload = _build_payload(generation_request)
        temp_path = _write_payload(payload)
        try:
            uploaded_file = _upload_payload(client, temp_path)
            job = _create_batch_job(client, image_model, uploaded_file.name)
            completed_job = _wait_for_completion(client, job.name)

            if completed_job is None:
                result = ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error="Batch job timed out",
                    error_code="TIMEOUT",
                )
            elif completed_job.state.name != "SUCCEEDED":
                error_msg = f"Batch job failed with state {completed_job.state.name}: {completed_job.error}"
                logger.error(error_msg)
                result = ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error=error_msg,
                    error_code="BATCH_FAILED",
                )
            else:
                data = _download_result(completed_job.output_uri)
                result = _extract_image(data)
        finally:
            _cleanup_temp_file(temp_path)

        if not result.has_image:
            error_message = result.error or "Image generation returned no data"
            logger.error("%s for post '%s'", error_message, input_data.post_title)
            return BannerOutput(error=error_message, error_code=result.error_code)

        document = Document(
            content=result.image_bytes,
            type=DocumentType.MEDIA,
            metadata={
                "mime_type": result.mime_type,
                "source": image_model,
                "slug": input_data.slug,
                "language": input_data.language,
            },
        )
        return BannerOutput(document=document, debug_text=result.debug_text)

    except google_exceptions.GoogleAPICallError as e:
        logger.exception("Banner image generation failed for post '%s'", input_data.post_title)
        return BannerOutput(error=type(e).__name__, error_code="GENERATION_EXCEPTION")


def generate_banner(
    post_title: str,
    post_summary: str,
    slug: str | None = None,
    language: str = "pt-BR",
) -> BannerOutput:
    client = genai.Client()
    config = EgregoraConfig()
    image_model = config.models.banner
    input_data = BannerInput(
        post_title=post_title,
        post_summary=post_summary,
        slug=slug,
        language=language,
    )
    prompt = _build_image_prompt(input_data)

    try:
        generation_request = ImageGenerationRequest(
            prompt=prompt,
            response_modalities=config.image_generation.response_modalities,
            aspect_ratio=config.image_generation.aspect_ratio,
        )
        for attempt in Retrying(stop=RETRY_STOP, wait=RETRY_WAIT, retry=RETRY_IF, reraise=True):
            with attempt:
                return _generate_banner_image(client, input_data, image_model, generation_request)
    except google_exceptions.GoogleAPICallError as e:
        logger.exception("Banner generation failed after retries")
        return BannerOutput(error=type(e).__name__, error_code="GENERATION_FAILED")


def is_banner_generation_available() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
