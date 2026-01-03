"""Tests for writer agent tool implementations."""

from unittest.mock import MagicMock

from egregora.agents.tools.writer_tools import BannerResult, generate_banner_impl


def test_generate_banner_impl_handles_none_slug(monkeypatch):
    """Verify generate_banner_impl gracefully handles a None post_slug."""
    mock_context = MagicMock()
    mock_context.task_store = MagicMock()
    mock_context.run_id = "test-run"
    mock_context.output_sink.url_convention.canonical_url.return_value = "/media/images/a-title.jpg"

    result = generate_banner_impl(ctx=mock_context, post_slug=None, title="A Title", summary="A summary")

    assert isinstance(result, BannerResult)
    assert result.status == "scheduled"
    assert result.path == "media/images/a-title.jpg"
