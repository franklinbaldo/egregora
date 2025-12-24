
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



