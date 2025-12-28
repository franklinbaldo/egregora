"""Tests for the V3 feed-based banner generator."""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import MagicMock

import pytest

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora_v3.core.types import Document, DocumentType, Entry, Feed
from egregora_v3.engine.banner.feed_generator import FeedBannerGenerator


class MockImageGenerationProvider(ImageGenerationProvider):
    """A mock image generation provider for testing."""

    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.generate_called = False
        self.last_request = None

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.generate_called = True
        self.last_request = request
        if self.should_succeed:
            return ImageGenerationResult(
                image_bytes=b"fake-image-bytes",
                mime_type="image/png",
            )
        return ImageGenerationResult(
            image_bytes=None,
            mime_type=None,
            error="Generation failed",
            error_code="TEST_FAILURE",
        )


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


def test_generator_requires_provider():
    """Verify the generator raises TypeError if provider is missing."""
    with pytest.raises(TypeError):
        FeedBannerGenerator()


def test_generate_from_feed_success(task_feed: Feed):
    """Verify successful generation of a banner."""
    # Arrange
    mock_provider = MockImageGenerationProvider(should_succeed=True)
    generator = FeedBannerGenerator(provider=mock_provider)

    # Act
    result_feed = generator.generate_from_feed(task_feed)

    # Assert
    assert len(result_feed.entries) == 1
    assert mock_provider.generate_called

    result_doc = result_feed.entries[0]
    assert isinstance(result_doc, Document)
    assert result_doc.doc_type == DocumentType.MEDIA
    assert result_doc.title == "Banner: Test Title"
    assert result_doc.content_type == "image/png"
    assert "task_id" in result_doc.internal_metadata
    assert result_doc.internal_metadata["task_id"] == "test-entry"


def test_generate_from_feed_failure(task_feed: Feed):
    """Verify error document creation on failure."""
    # Arrange
    mock_provider = MockImageGenerationProvider(should_succeed=False)
    generator = FeedBannerGenerator(provider=mock_provider)

    # Act
    result_feed = generator.generate_from_feed(task_feed)

    # Assert
    assert len(result_feed.entries) == 1
    assert mock_provider.generate_called

    error_doc = result_feed.entries[0]
    assert isinstance(error_doc, Document)
    assert error_doc.doc_type == DocumentType.NOTE
    assert error_doc.title == "Error: Test Title"
    assert "TEST_FAILURE" in error_doc.internal_metadata.get("error_code", "")


def test_generator_creates_correct_prompt(task_feed: Feed):
    """LOCKING TEST: Verify the full pipeline from Entry to prompt is correct."""
    # Arrange
    mock_provider = MockImageGenerationProvider()
    generator = FeedBannerGenerator(provider=mock_provider)

    # Act
    generator.generate_from_feed(task_feed)

    # Assert
    assert mock_provider.generate_called
    generated_prompt = mock_provider.last_request.prompt
    original_entry = task_feed.entries[0]

    # This is a bit of a weak assertion, but it locks the core behavior:
    # the title and summary must make it into the final prompt.
    assert original_entry.title in generated_prompt
    assert original_entry.summary in generated_prompt
