"""Tests for writer agent tool implementations."""

from unittest.mock import MagicMock

from egregora.agents.tools.writer_tools import BannerResult, generate_banner_impl


def test_generate_banner_impl_handles_none_slug(monkeypatch):
    """Verify generate_banner_impl gracefully handles a None post_slug."""
    mock_context = MagicMock()
    mock_context.task_store = MagicMock()  # Enable the task store path

    # This test is for the async path, where slugify is called.
    result = generate_banner_impl(ctx=mock_context, post_slug=None, title="A Title", summary="A summary")

    assert isinstance(result, BannerResult)
    assert result.status == "failed"
    assert "Invalid post_slug" in result.error


def test_generate_banner_impl_fallback_failure(monkeypatch):
    """Verify generate_banner_impl handles synchronous generation failure."""
    from egregora.agents.banner.exceptions import BannerGenerationError
    from egregora.agents.tools import writer_tools

    mock_context = MagicMock()
    mock_context.task_store = None  # Force synchronous path

    def mock_generate_banner(*args, **kwargs):
        raise BannerGenerationError("Generation failed")

    monkeypatch.setattr(writer_tools, "generate_banner", mock_generate_banner)

    result = generate_banner_impl(ctx=mock_context, post_slug="slug", title="Title", summary="Summary")

    assert result.status == "failed"
    assert result.error == "Generation failed"
