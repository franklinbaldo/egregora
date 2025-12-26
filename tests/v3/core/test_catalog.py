"""Tests for V3 Content Library Facade."""

from typing import List, Optional
from unittest.mock import Mock

import pytest
from datetime import UTC, datetime

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType


class MockRepository(DocumentRepository):
    """A mock repository that satisfies the protocol for Pydantic."""

    def __init__(self):
        self.mock = Mock()

    def save(self, doc: Document) -> Document:
        return self.mock.save(doc)

    def get(self, doc_id: str) -> Optional[Document]:
        return self.mock.get(doc_id)

    def list(self, *, doc_type: Optional[DocumentType] = None) -> List[Document]:
        return self.mock.list(doc_type=doc_type)

    def delete(self, doc_id: str) -> None:
        self.mock.delete(doc_id)

    def count(self, *, doc_type: Optional[DocumentType] = None) -> int:
        return self.mock.count(doc_type=doc_type)


def test_content_library_facade():
    """Test that ContentLibrary routes to correct repositories."""
    mock_posts = MockRepository()
    mock_media = MockRepository()
    mock_profiles = MockRepository()
    mock_journal = MockRepository()
    mock_enrichments = MockRepository()

    library = ContentLibrary(
        posts=mock_posts,
        media=mock_media,
        profiles=mock_profiles,
        journal=mock_journal,
        enrichments=mock_enrichments,
    )

    # Test get_repo
    assert library.get_repo(DocumentType.POST) == mock_posts
    assert library.get_repo(DocumentType.MEDIA) == mock_media
    assert library.get_repo(DocumentType.PROFILE) == mock_profiles
    assert library.get_repo(DocumentType.NOTE) == mock_journal

    # Test save
    doc = Document(
        doc_type=DocumentType.POST,
        title="Test",
        content="Content",
        updated=datetime.now(UTC),
    )
    library.save(doc)
    mock_posts.mock.save.assert_called_once_with(doc)

    # Test get (search all)
    mock_posts.mock.get.return_value = None
    mock_media.mock.get.return_value = doc

    result = library.get("some-id")
    assert result == doc
    mock_posts.mock.get.assert_called_with("some-id")
    mock_media.mock.get.assert_called_with("some-id")
