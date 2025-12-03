"""HTTP-based Gemini Batch client implementing the pydantic-ai Model interface."""

from __future__ import annotations

import base64
import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.usage import RequestUsage

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    tag: str
    response: dict[str, Any] | None
    error: dict[str, Any] | None


class GoogleBatchModel(Model):
    """Batch-backed Gemini model using the REST batch API."""

    _model_name: str
    poll_interval: float
    timeout: float
    api_key: str

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        poll_interval: float = 5.0,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(settings=None, profile=None)
        self.api_key = api_key

        # Normalize model name for Google API
        # Remove pydantic-ai provider prefix if present
        name = model_name.replace("google-gla:", "")
        # Ensure models/ prefix is present
        if not name.startswith("models/"):
            name = f"models/{name}"

        self._model_name = name
        self.poll_interval = poll_interval
        self.timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def system(self) -> str:
        return "google"

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        batch_results = self.run_batch(
            [
                {
                    "tag": "req-0",
                    "contents": self._to_genai_contents(messages),
                    "config": self._to_generation_config(model_settings, model_request_parameters),
                }
            ]
        )
        first = batch_results[0]
        if first.error:
            message = first.error.get("message") if isinstance(first.error, dict) else str(first.error)
            code = first.error.get("code") if isinstance(first.error, dict) else None
            if code == 429 or (message and "RESOURCE_EXHAUSTED" in message):
                raise UsageLimitExceeded(message or "Quota exceeded")
            raise ModelHTTPError(
                status_code=code or 0, model_name=self.model_name, body=message or str(first.error)
            )
        if not first.response:
            msg = f"No response returned for {self.model_name}"
            raise ModelAPIError(msg)

        text = self._extract_text(first.response)
        usage = RequestUsage()
        return ModelResponse(
            parts=[TextPart(text=text)], usage=usage, model_name=self.model_name, provider_name="google"
        )

    # ------------------------------------------------------------------ #
    # HTTP batch helpers
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------ #
    # HTTP batch helpers
    # ------------------------------------------------------------------ #
    def run_batch(self, requests: list[dict[str, Any]]) -> list[BatchResult]:
        """Run a batch of requests using the Gemini Batch API.

        Args:
            requests: List of request dictionaries. Each dict must have:
                - tag: Unique identifier for the request
                - contents: List of content parts (text/images)
                - config: Generation config (optional)

        Returns:
            List of BatchResult objects containing responses or errors.

        """
        # Import here to avoid circular dependencies
        from egregora.utils.network import get_retry_decorator

        if not requests:
            return []

        jsonl_lines = []
        for req in requests:
            record = {
                "key": req["tag"],
                "request": {
                    "contents": req["contents"],
                    "generation_config": req.get("config") or {},
                },
            }
            jsonl_lines.append(json.dumps(record))
        jsonl_body = "\n".join(jsonl_lines)

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        # Create a temporary file for upload
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
            f.write(jsonl_body)
            temp_path = f.name

        try:
            # Helper to wrap calls with retry
            retry_call = get_retry_decorator()

            # Upload file (blocking IO)
            uploaded_file = retry_call(
                lambda: client.files.upload(
                    file=temp_path,
                    config=types.UploadFileConfig(display_name="pydantic-ai-batch", mime_type="application/json"),
                )
            )

            # Create batch job (blocking IO)
            batch_job = retry_call(
                lambda: client.batches.create(
                    model=self.model_name,
                    src=uploaded_file.name,
                    config=types.CreateBatchJobConfig(display_name="pydantic-ai-batch"),
                )
            )

            # Poll for completion (sync poll)
            completed_job = self._poll_job(client, batch_job.name)

            # Download results (blocking IO)
            return self._download_results(client, completed_job.output_uri, requests)

        except genai.errors.ClientError as e:
            logger.exception("Google GenAI ClientError: %s", e)
            if e.code == 429:
                logger.exception("429 Details: %s", e.message)
                # Try to extract more details if available
                if hasattr(e, "details"):
                    logger.exception("Error Details: %s", e.details)

                msg = f"Google Batch API Quota Exceeded: {e.message}"
                raise UsageLimitExceeded(msg) from e
            raise ModelHTTPError(status_code=e.code, model_name=self.model_name, body=str(e)) from e

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _poll_job(self, client: Any, job_name: str) -> Any:
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            # client.batches.get is blocking
            job = client.batches.get(name=job_name)

            if job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED"):
                time.sleep(self.poll_interval)
                continue

            if job.state.name != "SUCCEEDED":
                raise ModelHTTPError(status_code=0, model_name=self.model_name, body=str(job.error))

            return job

        msg = "Batch job polling timed out"
        raise ModelAPIError(msg)

    def _download_results(
        self, client: Any, output_uri: str, requests: list[dict[str, Any]]
    ) -> list[BatchResult]:
        # httpx.get is blocking
        with httpx.Client() as http_client:
            resp = http_client.get(output_uri)
            resp.raise_for_status()

        lines = resp.text.splitlines()
        results: list[BatchResult] = []
        for idx, line in enumerate(lines):
            if not line.strip():
                continue
            data = json.loads(line)
            # Handle both successful response and error formats
            response = data.get("response")
            error = data.get("error")

            # Map key/custom_id back to tag
            tag = (
                data.get("key")
                or data.get("custom_id")
                or (requests[idx]["tag"] if idx < len(requests) else f"idx-{idx}")
            )

            results.append(BatchResult(tag=str(tag), response=response, error=error))
        return results

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _to_genai_contents(self, message_history: Iterable[ModelMessage]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for message in message_history:
            role = getattr(message, "role", None) or "user"
            text_parts: list[str] = []
            for part in getattr(message, "parts", []) or []:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "data") and part.data:  # binary content
                    b64 = base64.b64encode(part.data).decode("utf-8")
                    text_parts.append(f"<base64>{b64}")
            text = "\n".join(text_parts)
            contents.append({"role": role, "parts": [{"text": text}]})
        return contents

    def _to_generation_config(
        self, model_settings: ModelSettings | None, model_request_parameters: ModelRequestParameters | None
    ) -> dict[str, Any]:
        cfg: dict[str, Any] = {}
        if model_request_parameters and hasattr(model_request_parameters, "max_output_tokens"):
            cfg["max_output_tokens"] = model_request_parameters.max_output_tokens
        if model_settings and hasattr(model_settings, "response_modalities"):
            cfg["response_modalities"] = model_settings.response_modalities
        return cfg

    def _extract_text(self, response: dict[str, Any]) -> str:
        if not response:
            return ""
        # The SDK might return objects or dicts, but here we parsed JSON from output_uri
        if "text" in response:
            return response["text"]
        texts: list[str] = []
        for cand in response.get("candidates") or []:
            content = cand.get("content") or {}
            for part in content.get("parts") or []:
                if "text" in part:
                    texts.append(part["text"])
        return "\n".join(texts)
