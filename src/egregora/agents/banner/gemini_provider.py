"""Gemini implementation of the image generation abstraction."""

from __future__ import annotations

import base64
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

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
        payload = self._build_payload(request)
        temp_path = self._write_payload(payload)
        try:
            uploaded_file = self._upload_payload(temp_path)
            job = self._create_batch_job(uploaded_file.name)
            completed_job = self._wait_for_completion(job.name)
            if completed_job is None:
                return ImageGenerationResult(
                    image_bytes=None, mime_type=None, error="Batch job timed out", error_code="TIMEOUT"
                )

            if completed_job.state.name != "SUCCEEDED":
                error_msg = f"Batch job failed with state {completed_job.state.name}: {completed_job.error}"
                logger.error(error_msg)
                return ImageGenerationResult(
                    image_bytes=None, mime_type=None, error=error_msg, error_code="BATCH_FAILED"
                )

            data = self._download_result(completed_job.output_uri)
            return self._extract_image(data)
        finally:
            self._cleanup_temp_file(temp_path)

    def _build_payload(self, request: ImageGenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": "banner-req",
            "request": {
                "contents": [{"parts": [{"text": request.prompt}]}],
                "generation_config": {},
            },
        }
        if request.response_modalities:
            payload["request"]["generation_config"]["responseModalities"] = list(request.response_modalities)
        # if request.aspect_ratio:
        #     payload["request"]["generation_config"]["aspectRatio"] = request.aspect_ratio
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as temp_file:
            temp_file.write(json.dumps(payload) + "\n")
            return Path(temp_file.name)

    def _upload_payload(self, temp_path: Path) -> types.File:
        return self._client.files.upload(
            file=str(temp_path),
            config=types.UploadFileConfig(display_name="banner-batch", mime_type="application/json"),
        )

    def _create_batch_job(self, src: str) -> types.BatchJob:
        job = self._client.batches.create(
            model=self._model,
            src=src,
            config=types.CreateBatchJobConfig(display_name="banner-batch-job"),
        )
        logger.info("Created banner batch job: %s", job.name)
        return job

    def _wait_for_completion(self, job_name: str) -> types.BatchJob | None:
        start_time = time.time()
        while time.time() - start_time < self._timeout:
            job = self._client.batches.get(name=job_name)
            if job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED"):
                time.sleep(self._poll_interval)
                continue
            return job
        return None

    def _download_result(self, output_uri: str) -> dict[str, Any]:
        response = httpx.get(output_uri, timeout=self._timeout)
        response.raise_for_status()

        line = response.text.strip()
        if not line:
            return {"error": "Empty result file"}
        return json.loads(line)

    def _extract_image(self, data: dict[str, Any]) -> ImageGenerationResult:
        if "error" in data:
            return ImageGenerationResult(
                image_bytes=None, mime_type=None, error=str(data["error"]), error_code="GENERATION_ERROR"
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
                    image_bytes, mime_type = self._decode_inline_data(inline)

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

    def _decode_inline_data(self, inline: dict[str, Any]) -> tuple[bytes | None, str | None]:
        data_field = inline.get("data")
        image_bytes: bytes | None = None
        if isinstance(data_field, str):
            image_bytes = base64.b64decode(data_field)
        elif isinstance(data_field, bytes):
            image_bytes = data_field
        return image_bytes, inline.get("mimeType")

    def _cleanup_temp_file(self, temp_path: Path) -> None:
        if temp_path.exists():
            temp_path.unlink()
