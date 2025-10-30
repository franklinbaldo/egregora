"""
A playback client for replaying recorded Gemini API calls from golden fixtures.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from google.genai import types as genai_types

logger = logging.getLogger(__name__)


class FixtureNotFoundError(Exception):
    """Raised when a fixture for a given request hash is not found."""

    pass


class GeminiClientPlayback:
    """
    A client that replays recorded Gemini API calls from golden fixtures.

    This class reads a directory of recorded API calls (in JSON format) and
    uses them to respond to method calls, simulating the behavior of the
    actual `google.genai.Client`. It is a drop-in replacement for `genai.Client`
    for testing purposes.

    The client indexes fixtures by a SHA256 hash of the request content,
    allowing for fast lookups.

    Usage:
        fixtures_dir = Path("tests/fixtures/golden/api_responses")
        playback_client = GeminiClientPlayback(fixtures_dir)
        # Use playback_client as you would a real genai.Client
        response = playback_client.embed_content(...)
    """

    def __init__(self, fixtures_dir: Path):
        """
        Initializes the playback client and loads all fixtures.

        Args:
            fixtures_dir: The directory containing the golden fixture files.
        """
        self._fixtures_dir = fixtures_dir
        self._fixtures: Dict[str, Dict] = {}
        self._load_fixtures()

    def _load_fixtures(self):
        """Loads all .json fixtures from the specified directory into memory."""
        if not self._fixtures_dir.exists():
            raise FileNotFoundError(f"Fixtures directory not found: {self._fixtures_dir}")

        for filepath in self._fixtures_dir.glob("**/*.json"):
            with open(filepath, "r") as f:
                data = json.load(f)
                request_hash = self._hash_request(data["request"])
                self._fixtures[request_hash] = data["response"]
        logger.info(f"Loaded {len(self._fixtures)} fixtures from {self._fixtures_dir}")

    def _prepare_request_for_hashing(self, request_data: Dict) -> Dict:
        """Creates a deep copy of the request and makes it JSON serializable."""
        # Create a deep copy to avoid modifying the original request object
        def _convert_to_dict(obj):
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            elif isinstance(obj, Path):
                return str(obj)
            elif hasattr(obj, '__dict__'):
                return obj.__dict__
            return str(obj)

        data_copy = json.loads(json.dumps(request_data, default=_convert_to_dict))
        return data_copy

    def _hash_request(self, request_data: Dict) -> str:
        """
        Generates a SHA256 hash of the request data.
        This logic MUST be identical to GeminiClientRecorder._hash_request.
        """
        serializable_request = self._prepare_request_for_hashing(request_data)
        request_str = json.dumps(serializable_request, sort_keys=True)
        return hashlib.sha256(request_str.encode("utf-8")).hexdigest()

    def embed_content(self, **kwargs):
        """Replays an embedding API call from a fixture."""
        request_hash = self._hash_request(kwargs)
        if request_hash not in self._fixtures:
            raise FixtureNotFoundError(f"No fixture found for embed_content request with hash: {request_hash}")
        return self._fixtures[request_hash]

    @property
    def models(self):
        """Provides access to the models API."""

        class ModelsWrapper:
            def __init__(self, playback_client):
                self._playback_client = playback_client

            def generate_content(self, **kwargs):
                return self._playback_client._generate_content(**kwargs)

            def __getattr__(self, name):
                # Passthrough for other model attributes if needed
                raise NotImplementedError(f"'models.{name}' is not implemented in GeminiClientPlayback")

        return ModelsWrapper(self)

    def _generate_content(self, **kwargs):
        """Replays a content generation call from a fixture."""
        request_hash = self._hash_request(kwargs)
        if request_hash not in self._fixtures:
            raise FixtureNotFoundError(f"No fixture found for generate_content request with hash: {request_hash}")

        response_data = self._fixtures[request_hash]
        return genai_types.GenerateContentResponse.from_dict(response_data)


    @property
    def files(self):
        """Provides access to the files API."""

        class FilesWrapper:
            def __init__(self, playback_client):
                self._playback_client = playback_client

            def upload(self, **kwargs):
                return self._playback_client._upload_file(**kwargs)

            def __getattr__(self, name):
                raise NotImplementedError(f"'files.{name}' is not implemented in GeminiClientPlayback")

        return FilesWrapper(self)

    def _upload_file(self, **kwargs):
        """Replays a file upload call from a fixture."""
        # The recorder uses 'path' from the upload call in the request data
        path_str = str(kwargs.get('path', ''))
        request_data = {"path": path_str, **kwargs}
        request_hash = self._hash_request(request_data)

        if request_hash not in self._fixtures:
            raise FixtureNotFoundError(f"No fixture found for upload_file request with hash: {request_hash}")

        response_data = self._fixtures[request_hash]
        return genai_types.File(**response_data)

    def close(self):
        """A no-op close method to satisfy the client interface."""
        pass

    def __getattr__(self, name: str) -> Any:
        """
        Catch-all for any other methods to ensure the client is a good duck-type replacement.
        """
        raise NotImplementedError(f"'{name}' is not implemented in GeminiClientPlayback")