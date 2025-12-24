from unittest.mock import create_autospec

import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType


@pytest.fixture
def mock_posts_repo() -> DocumentRepository:
    """Fixture for a mock posts DocumentRepository."""
    return create_autospec(DocumentRepository, instance=True)


@pytest.fixture
def mock_media_repo() -> DocumentRepository:
    """Fixture for a mock media DocumentRepository."""
    return create_autospec(DocumentRepository, instance=True)


@pytest.fixture
def mock_profiles_repo() -> DocumentRepository:
    """Fixture for a mock profiles DocumentRepository."""
    return create_autospec(DocumentRepository, instance=True)


@pytest.fixture
def mock_journal_repo() -> DocumentRepository:
    """Fixture for a mock journal DocumentRepository."""
    return create_autospec(DocumentRepository, instance=True)


@pytest.fixture
def mock_enrichments_repo() -> DocumentRepository:
    """Fixture for a mock enrichments DocumentRepository."""
    return create_autospec(DocumentRepository, instance=True)


@pytest.fixture
def content_library(
    mock_posts_repo,
    mock_media_repo,
    mock_profiles_repo,
    mock_journal_repo,
    mock_enrichments_repo,
):
    """Fixture for a ContentLibrary with mock repositories."""
    return ContentLibrary(
        posts=mock_posts_repo,
        media=mock_media_repo,
        profiles=mock_profiles_repo,
        journal=mock_journal_repo,
        enrichments=mock_enrichments_repo,
    )


def test_content_library_repositories_property(
    content_library, mock_posts_repo, mock_media_repo
):
    """Test that ContentLibrary.repositories returns all repos."""
    repos = content_library.repositories
    assert len(repos) == 5
    assert mock_posts_repo in repos
    assert mock_media_repo in repos


def test_content_library_get_document_by_id(content_library, mock_media_repo):
    """Test that ContentLibrary.get finds a document across all repos."""
    # Arrange
    doc_id = "test-doc-id"
    from datetime import datetime, timezone
    doc = Document(
        id=doc_id,
        title="Test Doc",
        content="...",
        doc_type=DocumentType.POST,
        updated=datetime.now(timezone.utc)
    )

    # Configure mocks so only the 'media' repo finds the document
    for repo in content_library.repositories:
        repo.get.return_value = None
    mock_media_repo.get.return_value = doc

    # Act
    found_doc = content_library.get(doc_id)

    # Assert
    assert found_doc is not None
    assert found_doc.id == doc_id
    mock_media_repo.get.assert_called_once_with(doc_id)


def test_content_library_get_document_not_found(content_library):
    """Test that ContentLibrary.get returns None when doc is not found."""
    # Arrange
    doc_id = "not-found-id"
    for repo in content_library.repositories:
        repo.get.return_value = None

    # Act
    found_doc = content_library.get(doc_id)

    # Assert
    assert found_doc is None
    for repo in content_library.repositories:
        repo.get.assert_called_once_with(doc_id)
