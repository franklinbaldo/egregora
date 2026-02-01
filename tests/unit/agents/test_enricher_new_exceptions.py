import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from egregora.agents.enricher import (
    EnrichmentWorker,
    fetch_url_with_jina,
    load_file_as_binary_content,
    normalize_slug,
)
from egregora.agents.exceptions import (
    EnrichmentFileError,
    EnrichmentParsingError,
    EnrichmentSlugError,
    JinaFetchError,
)


@pytest.mark.asyncio
async def test_fetch_url_with_jina_raises_exception():
    """Test that Jina fetch failures raise JinaFetchError."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get.side_effect = httpx.RequestError("Network error")

        ctx = MagicMock()
        with pytest.raises(JinaFetchError, match="Jina fetch failed"):
            await fetch_url_with_jina(ctx, "http://example.com")


def testnormalize_slug_raises_exception():
    """Test that invalid slugs raise EnrichmentSlugError."""
    with pytest.raises(EnrichmentSlugError, match="LLM failed to generate slug"):
        normalize_slug(None, "id")

    with pytest.raises(EnrichmentSlugError, match=r"LLM slug .* is invalid"):
        normalize_slug("!@#$", "id")


def test_load_file_as_binary_content_raises_exception(tmp_path):
    """Test that file issues raise EnrichmentFileError."""
    # Missing file
    with pytest.raises(EnrichmentFileError, match="File not found"):
        load_file_as_binary_content(tmp_path / "missing.txt")

    # Large file
    large_file = tmp_path / "large.txt"
    # Create a small file but simulate large size via parameters
    large_file.write_bytes(b"content")

    # Actually, load_file_as_binary_content checks st_size.
    # To avoid creating a large file, we can just pass a very small max_size_mb
    # But max_size_mb is in MB. 0.000001 MB is 1 byte.

    large_file.write_bytes(b"12345")  # 5 bytes

    # 0.000001 * 1024 * 1024 = 1.04 bytes.
    with pytest.raises(EnrichmentFileError, match="File too large"):
        load_file_as_binary_content(large_file, max_size_mb=0.000001)


def test_parse_media_result_raises_exception():
    """Test that JSON parsing errors raise EnrichmentParsingError."""
    mock_ctx = MagicMock()
    # Mock task_store to avoid attribute error if it's accessed
    mock_ctx.task_store = MagicMock()
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "dummy"}):
        worker = EnrichmentWorker(ctx=mock_ctx)

    task = {"task_id": "1", "_parsed_payload": {"filename": "test.jpg"}}
    res = MagicMock()
    # Invalid JSON
    res.response = {"text": "{invalid json"}

    with pytest.raises(EnrichmentParsingError, match="Failed to parse media result"):
        worker.media_handler._parse_result(res, task)
