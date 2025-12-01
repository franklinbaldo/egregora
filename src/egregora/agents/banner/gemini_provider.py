"""Gemini implementation of the image generation abstraction."""

from __future__ import annotations

import logging

from google import genai

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
        import json
        import os
        import tempfile
        import time
        from google.genai import types

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
                config=types.UploadFileConfig(display_name='banner-batch', mime_type='application/json')
            )
            
            # 3. Create batch job
            batch_job = self._client.batches.create(
                model=self._model,
                src=uploaded_file.name,
                config=types.CreateBatchJobConfig(display_name='banner-batch-job')
            )
            logger.info("Created banner batch job: %s", batch_job.name)

            # 4. Poll for completion
            start_time = time.time()
            while time.time() - start_time < self._timeout:
                job = self._client.batches.get(name=batch_job.name)
                if job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED"):
                    time.sleep(self._poll_interval)
                    continue
                
                if job.state.name != "SUCCEEDED":
                    error_msg = f"Batch job failed with state {job.state.name}: {job.error}"
                    logger.error(error_msg)
                    return ImageGenerationResult(
                        image_bytes=None,
                        mime_type=None,
                        error=error_msg,
                        error_code="BATCH_FAILED"
                    )
                break
            else:
                return ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error="Batch job timed out",
                    error_code="TIMEOUT"
                )

            # 5. Download and parse results
            # The output_uri is a URL we can GET
            import httpx
            resp = httpx.get(job.output_uri)
            resp.raise_for_status()
            
            # Parse JSONL response
            # There should be only one line since we sent one request
            line = resp.text.strip()
            if not line:
                return ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error="Empty result file",
                    error_code="EMPTY_RESULT"
                )
                
            data = json.loads(line)
            if "error" in data:
                 return ImageGenerationResult(
                    image_bytes=None,
                    mime_type=None,
                    error=str(data["error"]),
                    error_code="GENERATION_ERROR"
                )

            # Extract image from response
            # Structure: response -> candidates -> content -> parts -> inlineData
            candidates = data.get("response", {}).get("candidates", [])
            
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
                            import base64
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
                    error_code="NO_IMAGE"
                )

            return ImageGenerationResult(
                image_bytes=image_bytes,
                mime_type=mime_type,
                debug_text=debug_text
            )

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
