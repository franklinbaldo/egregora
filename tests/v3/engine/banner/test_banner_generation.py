"""Tests for the V3 simplified banner generation function."""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import MagicMock

import pytest
from jinja2 import DictLoader, Environment, select_autoescape

from egregora.agents.banner.image_generation import (
    ImageGenerationProvider,
    ImageGenerationRequest,
    ImageGenerationResult,
)
from egregora_v3.core.types import Document, DocumentType, Entry
from egregora_v3.engine.banner.feed_generator import generate_banner_document


@pytest.fixture
def jinja_env() -> Environment:
    """Provides a simple Jinja2 environment for testing."""
    loader = DictLoader({"banner.jinja": "Prompt: {{ post_title }} - {{ post_summary }}"})
    return Environment(loader=loader, autoescape=select_autoescape())


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
def task_entry() -> Entry:
    """Provides a sample entry for banner generation."""
    now = datetime.now(UTC)
    return Entry(
        id="test-entry",
        title="Test Title",
        updated=now,
        summary="Test Summary",
        content="Test Content",
        internal_metadata={"slug": "test-title", "language": "en-US"},
    )


def test_generate_banner_document_from_entry_success(
    task_entry: Entry, jinja_env: Environment
):
    """Verify successful generation of a banner document from an entry."""
    # Arrange
    mock_provider = MockImageGenerationProvider(should_succeed=True)

    # Act
    result_doc = generate_banner_document(task_entry, mock_provider, jinja_env)

    # Assert
    assert isinstance(result_doc, Document)
    assert result_doc.doc_type == DocumentType.MEDIA
    assert result_doc.title == "Banner: Test Title"
    assert result_doc.content_type == "image/png"
    assert "task_id" in result_doc.internal_metadata
    assert result_doc.internal_metadata["task_id"] == "test-entry"


def test_generate_banner_document_from_entry_failure(
    task_entry: Entry, jinja_env: Environment
):
    """Verify error document creation on failure."""
    # Arrange
    mock_provider = MockImageGenerationProvider(should_succeed=False)

    # Act
    result_doc = generate_banner_document(task_entry, mock_provider, jinja_env)

    # Assert
    assert isinstance(result_doc, Document)
    assert result_doc.doc_type == DocumentType.NOTE
    assert result_doc.title == "Error: Test Title"
    assert "task_id" in result_doc.internal_metadata
    assert result_doc.internal_metadata["task_id"] == "test-entry"
    assert "error_code" in result_doc.internal_metadata
    assert result_doc.internal_metadata["error_code"] == "TEST_FAILURE"
