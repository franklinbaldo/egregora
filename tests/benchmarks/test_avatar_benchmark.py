import io
import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from PIL import Image

from egregora.agents.avatar import download_avatar_from_url


def generate_jpeg():
    img = Image.new("RGB", (100, 100), color="red")
    byte_io = io.BytesIO()
    img.save(byte_io, "JPEG")
    return byte_io.getvalue()


BASE_IMAGE_CONTENT = generate_jpeg()

# Unwrap the function to bypass rate limits
raw_download_func = download_avatar_from_url.__wrapped__.__wrapped__


@pytest.fixture
def mock_httpx_stream():
    # We patch the stream method on the actual class so we can use real Client init
    with patch("httpx.Client.stream") as mock_stream:

        def stream_side_effect(method, url, **kwargs):
            suffix = str(uuid.uuid4()).encode()
            content = BASE_IMAGE_CONTENT + suffix

            mock_resp_instance = MagicMock()
            mock_resp_instance.headers = {"content-type": "image/jpeg", "content-length": str(len(content))}

            def iter_bytes(chunk_size=8192):
                for i in range(0, len(content), chunk_size):
                    yield content[i : i + chunk_size]

            mock_resp_instance.iter_bytes = iter_bytes
            mock_resp_instance.raise_for_status = MagicMock()

            context = MagicMock()
            context.__enter__.return_value = mock_resp_instance
            context.__exit__.return_value = None
            return context

        mock_stream.side_effect = stream_side_effect
        yield mock_stream


def test_download_avatar_benchmark_new_client(benchmark, tmp_path, mock_httpx_stream):
    """Benchmark creating a new client every time (legacy path)."""
    _ = mock_httpx_stream  # Keep fixture alive
    media_dir = tmp_path / "media_new"
    url = "http://example.com/avatar.jpg"

    def run():
        # This will create a REAL httpx.Client (slow) but mock the network call
        raw_download_func(url, media_dir, client=None)

    benchmark(run)


def test_download_avatar_benchmark_reused_client(benchmark, tmp_path, mock_httpx_stream):
    """Benchmark reusing the client."""
    _ = mock_httpx_stream  # Keep fixture alive
    media_dir = tmp_path / "media_reused"
    url = "http://example.com/avatar.jpg"

    # Create one real client
    client = httpx.Client()

    def run():
        raw_download_func(url, media_dir, client=client)

    benchmark(run)

    client.close()
