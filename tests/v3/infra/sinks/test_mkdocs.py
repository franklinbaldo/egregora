"""Tests for the MkDocsOutputSink."""
from unittest.mock import MagicMock
import pytest
from textwrap import dedent

from pathlib import Path
from egregora_v3.core.types import Feed, Document, DocumentStatus, DocumentType, Author
from egregora_v3.infra.sinks.mkdocs import MkDocsOutputSink
from datetime import datetime, UTC

@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for the sink."""
    return tmp_path / "mkdocs_site"

@pytest.fixture
def published_doc() -> Document:
    """Create a sample published document."""
    return Document(
        id="published-doc",
        title="Published Doc",
        updated=datetime(2025, 12, 26, 18, 0, 0, tzinfo=UTC),
        published=datetime(2025, 12, 26, 18, 0, 0, tzinfo=UTC),
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        content="This is a published document.",
        authors=[Author(name="Author One")],
    )

@pytest.fixture
def another_published_doc() -> Document:
    """Create another sample published document to test sorting."""
    return Document(
        id="another-doc",
        title="Another Doc",
        updated=datetime(2025, 12, 27, 18, 0, 0, tzinfo=UTC),
        published=datetime(2025, 12, 27, 18, 0, 0, tzinfo=UTC),
        doc_type=DocumentType.POST,
        status=DocumentStatus.PUBLISHED,
        content="This is another published document.",
        authors=[Author(name="Author Two")],
    )

@pytest.fixture
def draft_doc() -> Document:
    """Create a sample draft document."""
    return Document(
        id="draft-doc",
        title="Draft Doc",
        updated=datetime.now(UTC),
        doc_type=DocumentType.NOTE,
        status=DocumentStatus.DRAFT,
        content="This is a draft document.",
    )


def test_publish_delegates_to_feed_for_published_docs(
    temp_output_dir: Path,
    published_doc: Document,
    draft_doc: Document,
    mocker,
):
    """
    Test that MkDocsOutputSink.publish uses Feed.get_published_documents
    to filter documents instead of implementing its own logic.
    """
    # Arrange
    sink = MkDocsOutputSink(temp_output_dir)
    feed = Feed(
        id="test-feed",
        title="Test Feed",
        updated=datetime.now(UTC),
        entries=[published_doc, draft_doc],
    )

    # Spy on the Feed class method, not the instance, to avoid Pydantic issues.
    get_published_docs_spy = mocker.spy(Feed, "get_published_documents")

    # Mock the write methods since we are not testing them here
    mocker.patch.object(sink, "_write_document")
    mocker.patch.object(sink, "_write_index")

    # Act
    sink.publish(feed)

    # Assert
    assert get_published_docs_spy.call_count == 1
