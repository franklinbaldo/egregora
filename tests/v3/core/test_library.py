
from unittest.mock import Mock, patch
import pytest

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType


@pytest.fixture
def mock_library() -> ContentLibrary:
    """Provides a ContentLibrary with mocked repositories."""
    return ContentLibrary(
        posts=Mock(spec=DocumentRepository),
        media=Mock(spec=DocumentRepository),
        profiles=Mock(spec=DocumentRepository),
        journal=Mock(spec=DocumentRepository),
        enrichments=Mock(spec=DocumentRepository),
    )


@pytest.mark.parametrize(
    "doc_type, repo_name",
    [
        (DocumentType.POST, "posts"),
        (DocumentType.MEDIA, "media"),
        (DocumentType.PROFILE, "profiles"),
        (DocumentType.NOTE, "journal"),  # NOTE maps to journal
        (DocumentType.ENRICHMENT, "enrichments"),
    ],
)
def test_content_library_routing(mock_library: ContentLibrary, doc_type: DocumentType, repo_name: str):
    """Test that documents are saved to the correct repository based on their type."""
    # Arrange
    doc = Document.create(content=f"Content for {doc_type.value}", doc_type=doc_type, title=f"Title {doc_type.value}")
    target_repo: Mock = getattr(mock_library, repo_name)

    # Act
    mock_library.save(doc)

    # Assert
    target_repo.save.assert_called_once_with(doc)

    # Also assert that other repos were NOT called
    all_repos = {
        "posts": mock_library.posts,
        "media": mock_library.media,
        "profiles": mock_library.profiles,
        "journal": mock_library.journal,
        "enrichments": mock_library.enrichments,
    }
    for name, repo in all_repos.items():
        if name != repo_name:
            repo.save.assert_not_called()


def test_content_library_fallback_routing(mock_library: ContentLibrary):
    """Test that an unknown document type falls back to the posts repository."""
    # Arrange
    doc = Document.create(content="Unknown content", doc_type=DocumentType.POST, title="Unknown title")
    # Patch the doc_type to be a value that doesn't exist in the enum
    doc.doc_type = "unknown_doc_type"

    # Act
    mock_library.save(doc)

    # Assert
    # The current implementation falls back to 'posts' repo
    mock_library.posts.save.assert_called_once_with(doc)
    mock_library.media.save.assert_not_called()
    mock_library.profiles.save.assert_not_called()
    mock_library.journal.save.assert_not_called()
    mock_library.enrichments.save.assert_not_called()
