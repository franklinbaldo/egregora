"""
A recorder for Gemini API calls to generate golden test fixtures.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar

import google.generativeai as genai
from google.generativeai.client import GenerativeServiceClient
from google.generativeai.generative_models import GenerativeModel, Part
from google.generativeai.client import FileServiceClient
from google.generativeai.files import File

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GeminiClientRecorder:
    """
    A wrapper around `google.generativeai.Client` that records API calls.

    This class intercepts calls to the Gemini API, executes them against the real
    API, and saves the request and response data to a specified directory. The
    recorded data can then be used as "golden fixtures" for testing, allowing
    tests to run without making live API calls.

    It is designed to be a drop-in replacement for `genai.Client`.

    Usage:
        client = genai.Client()
        recorder = GeminiClientRecorder(client, output_dir="tests/fixtures/golden/api_responses")
        # Now use `recorder` as you would use `client`
        recorder.embed_content(...)
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

    def _get_model(self, model_name: str) -> "GenerativeModel":
        """Wraps a model to ensure its calls are also recorded."""
        model = self._client.get_model(model_name)
        # It's easier to just monkey-patch the methods on the model instance
        # than to create a full wrapper class for GenerativeModel.
        original_embed_content = model.embed_content
        original_generate_content = model.generate_content

        def recorded_embed_content(*args, **kwargs):
            response = original_embed_content(*args, **kwargs)
            self._record_request("embeddings", kwargs, response.to_dict())
            return response

        def recorded_generate_content(*args, **kwargs):
            response = original_generate_content(*args, **kwargs)
            self._record_request("generation", kwargs, response.to_dict())
            return response

        model.embed_content = recorded_embed_content
        model.generate_content = recorded_generate_content
        return model

    def get_model(self, model_name: str) -> "GenerativeModel":
        return self._get_model(model_name)

    def embed_content(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Records an `embed_content` call.
        """
        response = self._client.embed_content(*args, **kwargs)
        self._record_request("embeddings", kwargs, response)
        return response

    def generate_content(self, *args, **kwargs) -> Any:
        """
        Records a `generate_content` call.
        """
        response = self._client.generate_content(*args, **kwargs)
        self._record_request("generation", kwargs, response.to_dict())
        return response

    def upload_file(self, path: str, **kwargs) -> File:
        """
        Records a `upload_file` call.
        """
        response = self._client.upload_file(path, **kwargs)
        request_data = {"path": path, **kwargs}
        self._record_request("files", request_data, response.to_dict())
        return response

    def _record_request(self, category: str, request_data: Dict, response_data: Dict):
        """
        Saves the request and response data to a file.
        """
        category_dir = self._output_dir / category
        category_dir.mkdir(exist_ok=True)

        # Convert Parts to dicts for stable hashing
        if 'content' in request_data and isinstance(request_data['content'], Part):
             request_data['content'] = request_data['content'].to_dict()
        if 'contents' in request_data:
            request_data['contents'] = [
                part.to_dict() if isinstance(part, Part) else part
                for part in request_data['contents']
            ]

        request_hash = self._hash_request(request_data)
        filename = f"response_{request_hash}.json"
        filepath = category_dir / filename

        if filepath.exists():
            logger.info(f"Skipping existing fixture for {category}: {filepath.name}")
            return

        fixture_data = {
            "request": request_data,
            "response": response_data,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(fixture_data, f, indent=2)
            logger.info(f"Recorded {category} to {filepath.name}")
        except Exception as e:
            logger.error(f"Failed to record {category} to {filepath.name}: {e}")

    def _hash_request(self, request_data: Dict) -> str:
        """
        Generates a SHA256 hash of the request data.
        """
        # Using a custom serializer to handle non-serializable types like Part
        def json_serializer(obj):
            if isinstance(obj, Part):
                return obj.to_dict()
            if isinstance(obj, Path):
                return str(obj)
            try:
                return obj.__dict__
            except AttributeError:
                return str(obj)

        request_str = json.dumps(request_data, sort_keys=True, default=json_serializer)
        return hashlib.sha256(request_str.encode("utf-8")).hexdigest()

    def __getattr__(self, name: str) -> Any:
        """
        Delegates any other attribute access to the wrapped client.
        This makes the recorder a transparent proxy.
        """
        return getattr(self._client, name)