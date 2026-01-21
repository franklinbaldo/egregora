from unittest.mock import MagicMock

import httpx
import pytest

from egregora.agents.avatar import (
    AvatarProcessingError,
    _download_image_content,
)

# Create a 5MB dummy image
# Start with JPEG magic bytes
DUMMY_IMAGE_SIZE = 5 * 1024 * 1024
DUMMY_IMAGE = b"\xff\xd8\xff" + b"\x00" * (DUMMY_IMAGE_SIZE - 3)

# 5MB of garbage
INVALID_IMAGE = b"\x00" * DUMMY_IMAGE_SIZE


def mock_response_iter_bytes(data, chunk_size=8192):
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


@pytest.fixture
def mock_response():
    response = MagicMock(spec=httpx.Response)
    response.headers = {"content-type": "image/jpeg", "content-length": str(len(DUMMY_IMAGE))}
    response.iter_bytes = lambda chunk_size=8192: mock_response_iter_bytes(DUMMY_IMAGE, chunk_size)
    return response


@pytest.fixture
def mock_invalid_response():
    response = MagicMock(spec=httpx.Response)
    response.headers = {"content-type": "image/jpeg", "content-length": str(len(INVALID_IMAGE))}
    response.iter_bytes = lambda chunk_size=8192: mock_response_iter_bytes(INVALID_IMAGE, chunk_size)
    return response


def test_download_image_content_benchmark(benchmark, mock_response):
    """Benchmark _download_image_content (valid)."""

    def run_download():
        _download_image_content(mock_response)

    benchmark(run_download)


def test_download_invalid_image_content_benchmark(benchmark, mock_invalid_response):
    """Benchmark _download_image_content (invalid)."""

    def run_download():
        try:
            _download_image_content(mock_invalid_response)
        except AvatarProcessingError:
            pass

    benchmark(run_download)
