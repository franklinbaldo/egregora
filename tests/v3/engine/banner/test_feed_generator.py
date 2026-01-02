"""Tests for the V3 feed-based banner generator."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from egregora.agents.banner.image_generation import ImageGenerationResult
from egregora_v3.core.types import Document, DocumentType, Entry, Feed
from egregora_v3.engine.banner.feed_generator import FeedBannerGenerator


@pytest.fixture
def task_feed() -> Feed:
    """Provides a sample feed of banner generation tasks."""
    now = datetime.now(UTC)
    entry = Entry(
        id="test-entry",
        title="Test Title",
        updated=now,
        summary="Test Summary",
        content="Test Content",
        internal_metadata={"slug": "test-title", "language": "en-US"},
    )
    return Feed(id="test-feed", title="Test Feed", updated=now, entries=[entry])


def test_generate_from_feed_success(task_feed: Feed):
    """Verify successful generation of a banner."""
    # Arrange
    generator = FeedBannerGenerator()
    success_doc = Document(
        doc_type=DocumentType.MEDIA,
        title="Banner: Test Title",
        content="fake-image-bytes",
        content_type="image/png",
        internal_metadata={"task_id": "test-entry"},
    )

    # Act
    with patch(
        "egregora_v3.engine.banner.feed_generator.generate_banner_document"
    ) as mock_generate:
        mock_generate.return_value = success_doc
        result_feed = generator.generate_from_feed(task_feed)

    # Assert
    assert len(result_feed.entries) == 1
    mock_generate.assert_called_once_with(task_feed.entries[0], generator.jinja_env)

    result_doc = result_feed.entries[0]
    assert result_doc.title == "Banner: Test Title"


def test_generate_from_feed_failure(task_feed: Feed):
    """Verify error document creation on failure."""
    # Arrange
    generator = FeedBannerGenerator()
    error_doc = Document(
        doc_type=DocumentType.NOTE,
        title="Error: Test Title",
        content="Generation failed",
        internal_metadata={"error_code": "TEST_FAILURE"},
    )

    # Act
    with patch(
        "egregora_v3.engine.banner.feed_generator.generate_banner_document"
    ) as mock_generate:
        mock_generate.return_value = error_doc
        result_feed = generator.generate_from_feed(task_feed)

    # Assert
    assert len(result_feed.entries) == 1
    mock_generate.assert_called_once_with(task_feed.entries[0], generator.jinja_env)

    result_doc = result_feed.entries[0]
    assert result_doc.title == "Error: Test Title"
    assert "TEST_FAILURE" in result_doc.internal_metadata.get("error_code", "")
