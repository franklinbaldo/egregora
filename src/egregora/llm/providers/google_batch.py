"""HTTP-based Gemini Batch client implementing the pydantic-ai Model interface."""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import httpx
from google import genai
from google.genai import types
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model, ModelRequestParameters, ModelSettings
from pydantic_ai.usage import RequestUsage
from tenacity import RetryError, retry, retry_if_result, stop_after_delay, wait_fixed

from egregora.llm.exceptions import (
    BatchJobFailedError,
    BatchJobTimeoutError,
    BatchResultDownloadError,
    InvalidLLMResponseError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429


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
            if code == HTTP_TOO_MANY_REQUESTS or (message and "RESOURCE_EXHAUSTED" in message):
                raise UsageLimitExceeded(message or "Quota exceeded")
            raise ModelHTTPError(
                status_code=code or 0, model_name=self.model_name, body=message or str(first.error)
            )
        if not first.response:
            msg = f"No response returned for model {self.model_name}"
            raise InvalidLLMResponseError(msg)

        text = self._extract_text(first.response)
        usage = RequestUsage()
        return ModelResponse(
            parts=[TextPart(content=text)], usage=usage, model_name=self.model_name, provider_name="google"
        )

    # ------------------------------------------------------------------ #
    # HTTP batch helpers
    # ------------------------------------------------------------------ #
    def run_batch(self, requests: list[dict[str, Any]]) -> list[BatchResult]:
        """Run a batch of requests using the Gemini Batch API with inline requests.

        Args:
            requests: List of request dictionaries. Each dict must have:
                - tag: Unique identifier for the request
                - contents: List of content parts (text/images)
                - config: Generation config (optional)

        Returns:
            List of BatchResult objects containing responses or errors.

        """
        if not requests:
            return []

        # Build inline requests (no file upload needed for <20MB)
        inline_requests = []
        for req in requests:
            inline_req = {
                "contents": req["contents"],
            }
            if req.get("config"):
                inline_req["generation_config"] = req["config"]
            inline_requests.append(inline_req)

        client = genai.Client(api_key=self.api_key)

        try:
            logger.info("[BatchAPI] Creating batch job with %d inline requests", len(inline_requests))

            # Create batch job with inline requests (no file upload)
            batch_job = client.batches.create(
                model=self.model_name,
                src=cast("Any", inline_requests),
                config=types.CreateBatchJobConfig(display_name="egregora-batch"),
            )

            logger.info("[BatchAPI] Batch job created: %s", batch_job.name)

            # Poll for completion
            completed_job = self._poll_job(client, batch_job.name)

            logger.info("[BatchAPI] Batch job completed: %s", completed_job.state.name)

            # Get results from inlineResponse (inline requests return inline responses)
            return self._extract_inline_results(completed_job, requests)

        except genai.errors.ClientError as e:
            if e.code == HTTP_TOO_MANY_REQUESTS:
                logger.warning("[BatchAPI] Quota exceeded: %s", e.message)
                msg = f"Google Batch API Quota Exceeded: {e.message}"
                raise UsageLimitExceeded(msg) from e
            logger.exception("[BatchAPI] ClientError")
            raise ModelHTTPError(status_code=e.code, model_name=self.model_name, body=str(e)) from e

    def _extract_inline_results(self, job: types.BatchJob, requests: list[dict[str, Any]]) -> list[BatchResult]:
        """Extract results from inline batch response."""
        results: list[BatchResult] = []

        # For inline requests, results come in job.dest.inline_responses
        inline_responses = getattr(job, "dest", None)
        if inline_responses and hasattr(inline_responses, "inline_responses"):
            responses = inline_responses.inline_responses or []
            for idx, resp in enumerate(responses):
                tag = requests[idx]["tag"] if idx < len(requests) else f"idx-{idx}"

                # Extract response or error
                if hasattr(resp, "error") and resp.error:
                    results.append(
                        BatchResult(
                            tag=tag,
                            response=None,
                            error={"message": str(resp.error), "code": getattr(resp.error, "code", None)},
                        )
                    )
                elif hasattr(resp, "response") and resp.response:
                    # Convert response to dict format expected by _extract_text
                    response_dict = self._response_to_dict(resp.response)
                    results.append(BatchResult(tag=tag, response=response_dict, error=None))
                else:
                    results.append(BatchResult(tag=tag, response=None, error={"message": "No response"}))
        else:
            # Fallback: try to get results from output_uri (file-based response)
            if hasattr(job, "output_uri") and job.output_uri:
                logger.info("[BatchAPI] Using output_uri for results: %s", job.output_uri)
                return self._download_results(genai.Client(api_key=self.api_key), job.output_uri, requests)

            # No results available
            for _idx, req in enumerate(requests):
                results.append(
                    BatchResult(
                        tag=req["tag"], response=None, error={"message": "No inline response available"}
                    )
                )

        return results

    # TODO: [Taskmaster] Refactor for clarity and conciseness
    def _response_to_dict(self, response: types.GenerateContentResponse | dict[str, Any]) -> dict[str, Any]:
        """Convert SDK response object to dict format."""
        if isinstance(response, dict):
            return response

        result: dict[str, Any] = {}
        if hasattr(response, "candidates"):
            candidates = []
            # types.GenerateContentResponse has candidates which is list[Candidate]
            for cand in response.candidates or []:
                cand_dict: dict[str, Any] = {}
                if hasattr(cand, "content") and cand.content:
                    content_dict: dict[str, Any] = {}
                    if hasattr(cand.content, "parts"):
                        content_dict["parts"] = [
                            {"text": part.text}
                            for part in (cand.content.parts or [])
                            if hasattr(part, "text")
                        ]
                    if hasattr(cand.content, "role"):
                        content_dict["role"] = cand.content.role
                    cand_dict["content"] = content_dict
                candidates.append(cand_dict)
            result["candidates"] = candidates
        return result

    def _poll_job(self, client: genai.Client, job_name: str) -> types.BatchJob:
        """Poll the batch job for completion using tenacity."""

        def _check_job_status(job: types.BatchJob) -> bool:
            return job.state.name in ("PROCESSING", "PENDING", "STATE_UNSPECIFIED")

        # Retry while the job is in a processing state
        # stop_after_delay corresponds to self.timeout
        # wait_fixed corresponds to self.poll_interval
        @retry(
            retry=retry_if_result(_check_job_status),
            stop=stop_after_delay(self.timeout),
            wait=wait_fixed(self.poll_interval),
            reraise=True,
        )
        def _get_job_with_retry() -> types.BatchJob:
            # client.batches.get is blocking
            return client.batches.get(name=job_name)

        try:
            job = _get_job_with_retry()
        except RetryError as e:
            # Tenacity raises RetryError when retries are exhausted (timeout)
            msg = "Batch job polling timed out"
            raise BatchJobTimeoutError(msg, job_name=job_name) from e

        if job.state.name != "SUCCEEDED":
            msg = "Batch job failed"
            raise BatchJobFailedError(
                msg,
                job_name=job_name,
                error_payload=cast("dict[str, Any] | None", job.error),
            )

        return job

    def _download_results(
        self, client: genai.Client, output_uri: str, requests: list[dict[str, Any]]
    ) -> list[BatchResult]:
        # httpx.get is blocking
        try:
            with httpx.Client() as http_client:
                resp = http_client.get(output_uri)
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            msg = "Failed to download batch results"
            raise BatchResultDownloadError(msg, url=output_uri) from e

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
        if model_settings:
            # ModelSettings is often a TypedDict, so we use .get()
            response_modalities = model_settings.get("response_modalities")
            if response_modalities:
                cfg["response_modalities"] = response_modalities
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
            texts.extend(part["text"] for part in content.get("parts") or [] if "text" in part)
        return "\n".join(texts)
