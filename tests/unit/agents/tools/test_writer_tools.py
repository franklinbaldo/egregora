"""Tests for writer agent tool implementations."""

import pytest
from unittest.mock import MagicMock
from egregora.agents.tools.writer_tools import generate_banner_impl, BannerResult

def test_generate_banner_impl_handles_none_slug(monkeypatch):
    """Verify generate_banner_impl gracefully handles a None post_slug."""
    mock_context = MagicMock()
    mock_context.task_store = MagicMock()  # Enable the task store path
    mock_context.run_id = "test-run"

    # This test is for the async path, where slugify is called.
    result = generate_banner_impl(
        ctx=mock_context,
        post_slug=None,
        title="A Title",
        summary="A summary"
    )

    assert isinstance(result, BannerResult)
    assert result.status == "failed"
    assert "Invalid post_slug" in result.error
