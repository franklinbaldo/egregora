"""
A recorder for Gemini API calls to generate golden test fixtures.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict

from google import genai
from google.generativeai.client import File, GenerativeModel
from google.generativeai.types import content_types

logger = logging.getLogger(__name__)


class GeminiClientRecorder:
    """
    A wrapper around `google.genai.Client` that records API calls.

    This class intercepts calls to the Gemini API, executes them against the real
    API, and saves the request and response data to a specified directory. The
    recorded data can then be used as "golden fixtures" for testing, allowing
    tests to run without making live API calls.

    It is designed to be a drop-in replacement for `genai.Client`.

    Usage:
        client = genai.Client()
        recorder = GeminiClientRecorder(client, output_dir="tests/fixtures/golden/api_responses")
        # Now use `recorder` as you would use `client`
        model = recorder.get_model("gemini-pro")
        model.generate_content(...)
    """

    def __init__(self, client: genai.client.Client, output_dir: Path):
        """
        Initializes the recorder.

        Args:
            client: The actual `genai.Client` instance to which calls will be delegated.
            output_dir: The directory where recorded fixtures will be saved.
        """
        self._client = client
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def get_model(self, model_name: str) -> "GenerativeModel":
        """
        Gets a model and wraps it to record its API calls.
        """
        model = self._client.get_model(model_name)
        # It's easier to just monkey-patch the methods on the model instance
        # than to create a full wrapper class for GenerativeModel.
        original_embed_content = model.embed_content
        original_generate_content = model.generate_content

        def recorded_embed_content(*args, **kwargs):
            response = original_embed_content(*args, **kwargs)
            self._record_request("embeddings", kwargs, response)
            return response

        def recorded_generate_content(*args, **kwargs):
            response = original_generate_content(*args, **kwargs)
            # The response object from generate_content is complex, so we convert to dict
            self._record_request("generation", kwargs, response.to_dict())
            return response

        model.embed_content = recorded_embed_content
        model.generate_content = recorded_generate_content
        return model

    def upload_file(self, path: str, **kwargs) -> File:
        """
        Records a `upload_file` call.
        """
        response = self._client.upload_file(path, **kwargs)
        request_data = {"path": str(path), **kwargs}
        self._record_request("files", request_data, response.to_dict())
        return response

    def _record_request(self, category: str, request_data: Dict, response_data: Dict):
        """
        Saves the request and response data to a file.
        """
        category_dir = self._output_dir / category
        category_dir.mkdir(exist_ok=True)

        # Convert Parts to dicts for stable hashing
        serializable_request = self._prepare_request_for_hashing(request_data)

        request_hash = self._hash_request(serializable_request)
        filename = f"response_{request_hash}.json"
        filepath = category_dir / filename

        if filepath.exists():
            logger.info(f"Skipping existing fixture for {category}: {filepath.name}")
            return

        fixture_data = {
            "request": serializable_request,
            "response": response_data,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(fixture_data, f, indent=2, default=str) # Use default=str for any other non-serializable types
            logger.info(f"Recorded {category} to {filepath.name}")
        except Exception as e:
            logger.error(f"Failed to record {category} to {filepath.name}: {e}")

    def _prepare_request_for_hashing(self, request_data: Dict) -> Dict:
        """Creates a deep copy of the request and makes it JSON serializable."""
        # Create a deep copy to avoid modifying the original request object
        data_copy = json.loads(json.dumps(request_data, default=content_types.to_dict))
        return data_copy


    def _hash_request(self, request_data: Dict) -> str:
        """
        Generates a SHA256 hash of the request data.
        """
        request_str = json.dumps(request_data, sort_keys=True)
        return hashlib.sha256(request_str.encode("utf-8")).hexdigest()

    def __getattr__(self, name: str) -> Any:
        """
        Delegates any other attribute access to the wrapped client.
        This makes the recorder a transparent proxy.
        """
        return getattr(self._client, name)