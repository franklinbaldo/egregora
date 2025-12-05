from unittest.mock import Mock

from egregora_v3.core.catalog import ContentLibrary
from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType


def test_content_library_routing():
    posts_repo = Mock(spec=DocumentRepository)
    media_repo = Mock(spec=DocumentRepository)
    profiles_repo = Mock(spec=DocumentRepository)
    journal_repo = Mock(spec=DocumentRepository)
    enrichments_repo = Mock(spec=DocumentRepository)

    lib = ContentLibrary(
        posts=posts_repo,
        media=media_repo,
        profiles=profiles_repo,
        journal=journal_repo,
        enrichments=enrichments_repo,
    )

    # Test POST routing
    doc_post = Document.create(content="A", doc_type=DocumentType.POST, title="A")
    lib.save(doc_post)
    posts_repo.save.assert_called_with(doc_post)

    # Test PROFILE routing
    doc_profile = Document.create(content="B", doc_type=DocumentType.PROFILE, title="B")
    lib.save(doc_profile)
    profiles_repo.save.assert_called_with(doc_profile)
