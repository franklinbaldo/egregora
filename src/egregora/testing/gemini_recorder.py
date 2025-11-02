"""
A recorder for Gemini API calls to generate golden test fixtures.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types as genai_types

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

    def __init__(self, client: genai.Client, output_dir: Path):
        """
        Initializes the recorder.

        Args:
            client: The actual `genai.Client` instance to which calls will be delegated.
            output_dir: The directory where recorded fixtures will be saved.
        """
        self._client = client
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def embed_content(self, **kwargs):
        """Record embedding API calls."""
        response = self._client.embed_content(**kwargs)
        # Convert response to dict for serialization
        response_dict = dict(response)
        self._record_request("embeddings", kwargs, response_dict)
        return response

    @property
    def models(self):
        """Provide access to models with recording."""

        # Return a wrapper that records generate_content calls
        class ModelsWrapper:
            def __init__(self, client, recorder):
                self._client = client
                self._recorder = recorder

            def generate_content(self, **kwargs):
                response = self._client.models.generate_content(**kwargs)
                # Convert response to dict
                response_dict = {
                    "text": response.text if hasattr(response, "text") else str(response),
                    "candidates": [
                        c.to_dict() if hasattr(c, "to_dict") else str(c)
                        for c in (response.candidates if hasattr(response, "candidates") else [])
                    ],
                }
                self._recorder._record_request("generation", kwargs, response_dict)
                return response

            def __getattr__(self, name):
                return getattr(self._client.models, name)

        return ModelsWrapper(self._client, self)

    def upload_file(self, path: str, **kwargs) -> genai_types.File:
        """
        Records a `upload_file` call.
        """
        response = self._client.files.upload(file=path, **kwargs)
        request_data = {"path": str(path), **kwargs}
        # Convert File object to dict
        response_dict = {
            "name": response.name if hasattr(response, "name") else str(response),
            "uri": response.uri if hasattr(response, "uri") else None,
        }
        self._record_request("files", request_data, response_dict)
        return response

    @property
    def files(self):
        """Provide access to files API with recording."""

        class FilesWrapper:
            def __init__(self, client, recorder):
                self._client = client
                self._recorder = recorder

            def upload(self, **kwargs):
                return self._recorder.upload_file(
                    **kwargs.get("file", kwargs.get("path", "")), **kwargs
                )

            def __getattr__(self, name):
                return getattr(self._client.files, name)

        return FilesWrapper(self._client, self)

    def _record_request(self, category: str, request_data: dict, response_data: dict):
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
                json.dump(
                    fixture_data, f, indent=2, default=str
                )  # Use default=str for any other non-serializable types
            logger.info(f"Recorded {category} to {filepath.name}")
        except Exception as e:
            logger.error(f"Failed to record {category} to {filepath.name}: {e}")

    def _prepare_request_for_hashing(self, request_data: dict) -> dict:
        """Creates a deep copy of the request and makes it JSON serializable."""

        # Create a deep copy to avoid modifying the original request object
        def _convert_to_dict(obj):
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            elif hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)

        data_copy = json.loads(json.dumps(request_data, default=_convert_to_dict))
        return data_copy

    def _hash_request(self, request_data: dict) -> str:
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
