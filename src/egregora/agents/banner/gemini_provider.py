"""Gemini implementation of the image generation abstraction.

This module implements the image generation provider using Google's GenAI Batch API.
Refactored to move inline imports to top-level and replace tight polling loops.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import time

import httpx
from google import genai
from google.genai import types

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)

logger = logging.getLogger(__name__)


class GeminiImageGenerationProvider(ImageGenerationProvider):
    """Generate images using the Gemini Batch API."""

    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self._model = model
        self._poll_interval = 10.0
        self._timeout = 600.0  # 10 minutes for batch

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate image using Batch API lifecycle."""
        # 1. Prepare JSONL payload
        payload = {
            "key": "banner-req",
            "request": {
                "contents": [{"parts": [{"text": request.prompt}]}],
                "generation_config": {},
            },
        }

        if request.response_modalities:
            payload["request"]["generation_config"]["responseModalities"] = list(request.response_modalities)
        if request.aspect_ratio:
            payload["request"]["generation_config"]["aspectRatio"] = request.aspect_ratio

        # 2. Create temp file and upload
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
            f.write(json.dumps(payload) + "\n")
            temp_path = f.name

        try:
            uploaded_file = self._client.files.upload(
                file=temp_path,
                config=types.UploadFileConfig(display_name="banner-batch", mime_type="application/json"),
            )

            # 3. Create batch job
            batch_job = self._client.batches.create(
                model=self._model,
                src=uploaded_file.name,
                config=types.CreateBatchJobConfig(display_name="banner-batch-job"),
            )
            logger.info("Created banner batch job: %s", batch_job.name)

            # 4. Poll for completion
            final_job = self._wait_for_completion(batch_job.name)

            if final_job.state.name != "SUCCEEDED":
                error_msg = f"Batch job failed with state {final_job.state.name}: {final_job.error}"
                logger.error(error_msg)
                return ImageGenerationResult(
                    image_bytes=None, mime_type=None, error=error_msg, error_code="BATCH_FAILED"
                )

            # 5. Download and parse results
            resp = httpx.get(final_job.output_uri)
            resp.raise_for_status()

            # Parse JSONL response
            # There should be only one line since we sent one request
            line = resp.text.strip()
            if not line:
                return ImageGenerationResult(
                    image_bytes=None, mime_type=None, error="Empty result file", error_code="EMPTY_RESULT"
                )

            data = json.loads(line)
            if "error" in data:
                return ImageGenerationResult(
                    image_bytes=None, mime_type=None, error=str(data["error"]), error_code="GENERATION_ERROR"
                )

            # Extract image from response
            return self._parse_candidates(data.get("response", {}).get("candidates", []))

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _wait_for_completion(self, job_name: str) -> types.BatchJob:
        """Poll for batch job completion with timeout."""
        start_time = time.time()
        while time.time() - start_time < self._timeout:
            job = self._client.batches.get(name=job_name)
            if job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED"):
                time.sleep(self._poll_interval)
                continue
            return job

        raise TimeoutError("Batch job timed out")

    def _parse_candidates(self, candidates: list[dict]) -> ImageGenerationResult:
        """Extract image and text from candidates list."""
        image_bytes: bytes | None = None
        mime_type: str | None = None
        debug_text_parts: list[str] = []

        for cand in candidates:
            for part in cand.get("content", {}).get("parts", []):
                if "text" in part:
                    debug_text_parts.append(part["text"])
                if "inlineData" in part and image_bytes is None:
                    inline = part["inlineData"]
                    data_field = inline.get("data")
                    if isinstance(data_field, str):
                        image_bytes = base64.b64decode(data_field)
                    else:
                        image_bytes = data_field
                    mime_type = inline.get("mimeType")

        debug_text = "\n".join(debug_text_parts) if debug_text_parts else None

        if image_bytes is None:
            return ImageGenerationResult(
                image_bytes=None,
                mime_type=None,
                debug_text=debug_text,
                error="No image data found in response",
                error_code="NO_IMAGE",
            )

        return ImageGenerationResult(image_bytes=image_bytes, mime_type=mime_type, debug_text=debug_text)
