"""Gemini Batch API implementation for handling large content processing."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    from google.genai import types as genai_types  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    genai_types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class BatchJobState(Enum):
    """Batch job states according to Gemini Batch API."""
    STATE_UNSPECIFIED = "STATE_UNSPECIFIED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(slots=True)
class BatchRequest:
    """Individual request in a batch."""
    custom_id: str
    method: str
    uri: str
    body: Dict[str, Any]


@dataclass(slots=True)
class BatchResponse:
    """Individual response from a batch."""
    custom_id: str
    response: Dict[str, Any]
    error: Optional[Dict[str, Any]] = None


@dataclass(slots=True)
class BatchJob:
    """Batch job metadata."""
    name: str
    state: BatchJobState
    create_time: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    request_count: Optional[int] = None
    error: Optional[Dict[str, Any]] = None


class GeminiBatchClient:
    """Client for Gemini Batch API operations."""

    def __init__(self, client: object, *, model: str = "gemini-1.5-flash"):
        if genai_types is None:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "google-genai must be installed to use Gemini Batch API"
            ) from None
        
        self.client = client
        self.model = model

    def create_batch_job(
        self,
        requests: List[BatchRequest],
        *,
        display_name: Optional[str] = None,
    ) -> str:
        """Create a batch job and return the job name."""
        
        # Convert requests to JSONL format
        jsonl_lines = []
        for request in requests:
            jsonl_lines.append(json.dumps({
                "custom_id": request.custom_id,
                "method": request.method,
                "uri": request.uri,
                "body": request.body
            }))
        
        requests_jsonl = "\n".join(jsonl_lines)
        
        # Create batch job request
        try:
            response = self.client.batches.create(  # type: ignore[call-arg]
                requests=requests_jsonl,
                model=self.model,
                **({"display_name": display_name} if display_name else {})
            )
            
            job_name = getattr(response, "name", None)
            if not job_name:
                raise RuntimeError("Failed to get job name from batch creation response")
            
            logger.info("Created batch job: %s", job_name)
            return job_name
            
        except Exception as exc:
            logger.error("Failed to create batch job: %s", exc)
            raise

    def get_batch_job(self, job_name: str) -> BatchJob:
        """Get batch job status and metadata."""
        
        try:
            response = self.client.batches.get(name=job_name)  # type: ignore[call-arg]
            
            state_str = getattr(response, "state", "STATE_UNSPECIFIED")
            state = BatchJobState(state_str) if state_str in BatchJobState.__members__.values() else BatchJobState.STATE_UNSPECIFIED
            
            return BatchJob(
                name=getattr(response, "name", job_name),
                state=state,
                create_time=getattr(response, "create_time", ""),
                start_time=getattr(response, "start_time", None),
                end_time=getattr(response, "end_time", None),
                request_count=getattr(response, "request_count", None),
                error=getattr(response, "error", None),
            )
            
        except Exception as exc:
            logger.error("Failed to get batch job %s: %s", job_name, exc)
            raise

    def wait_for_completion(
        self,
        job_name: str,
        *,
        timeout_seconds: int = 3600,
        poll_interval_seconds: int = 30,
    ) -> BatchJob:
        """Wait for batch job to complete."""
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            job = self.get_batch_job(job_name)
            
            if job.state in (BatchJobState.COMPLETED, BatchJobState.FAILED, BatchJobState.CANCELLED):
                logger.info("Batch job %s finished with state: %s", job_name, job.state.value)
                return job
            
            logger.debug("Batch job %s state: %s", job_name, job.state.value)
            time.sleep(poll_interval_seconds)
        
        raise TimeoutError(f"Batch job {job_name} did not complete within {timeout_seconds} seconds")

    def get_batch_responses(self, job_name: str) -> List[BatchResponse]:
        """Get responses from a completed batch job."""
        
        try:
            response = self.client.batches.get(name=job_name)  # type: ignore[call-arg]
            
            # Get the response JSONL content
            responses_jsonl = getattr(response, "responses", None)
            if not responses_jsonl:
                logger.warning("No responses found for batch job %s", job_name)
                return []
            
            # Parse JSONL responses
            responses = []
            for line in responses_jsonl.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    response_data = json.loads(line)
                    responses.append(BatchResponse(
                        custom_id=response_data["custom_id"],
                        response=response_data.get("response", {}),
                        error=response_data.get("error"),
                    ))
                except json.JSONDecodeError as exc:
                    logger.warning("Failed to parse response line: %s", exc)
                    continue
            
            return responses
            
        except Exception as exc:
            logger.error("Failed to get batch responses for %s: %s", job_name, exc)
            raise

    def cancel_batch_job(self, job_name: str) -> None:
        """Cancel a running batch job."""
        
        try:
            self.client.batches.cancel(name=job_name)  # type: ignore[call-arg]
            logger.info("Cancelled batch job: %s", job_name)
            
        except Exception as exc:
            logger.error("Failed to cancel batch job %s: %s", job_name, exc)
            raise


def create_embedding_batch_requests(
    texts: List[str],
    *,
    model: str = "models/text-embedding-004",
    batch_size: int = 100,
) -> List[BatchRequest]:
    """Create batch requests for text embedding."""
    
    requests = []
    
    for i, text in enumerate(texts):
        if i >= batch_size:
            break
            
        request = BatchRequest(
            custom_id=f"embedding_{i}",
            method="POST",
            uri=f"/v1beta/models/{model}:embedContent",
            body={
                "content": {
                    "parts": [{"text": text}]
                }
            }
        )
        requests.append(request)
    
    return requests


def create_generation_batch_requests(
    prompts: List[str],
    *,
    model: str = "gemini-1.5-flash",
    system_instruction: Optional[str] = None,
    batch_size: int = 50,
) -> List[BatchRequest]:
    """Create batch requests for content generation."""
    
    requests = []
    
    for i, prompt in enumerate(prompts):
        if i >= batch_size:
            break
        
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }
        
        if system_instruction:
            body["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }
        
        request = BatchRequest(
            custom_id=f"generation_{i}",
            method="POST", 
            uri=f"/v1beta/models/{model}:generateContent",
            body=body
        )
        requests.append(request)
    
    return requests


__all__ = [
    "BatchJobState",
    "BatchRequest", 
    "BatchResponse",
    "BatchJob",
    "GeminiBatchClient",
    "create_embedding_batch_requests",
    "create_generation_batch_requests",
]