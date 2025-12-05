"""Content Library Facade.

This module replaces the AtomPub-style Catalog (Service/Workspace/Collection)
with a simpler Repository Pattern facade.

It exposes typed repositories for accessing and persisting content.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import DocumentType

if TYPE_CHECKING:
    from egregora_v3.core.types import Document

logger = logging.getLogger(__name__)


class ContentLibrary(BaseModel):
    """Facade for content repositories.

    Replaces the complex Service/Workspace/Collection hierarchy.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    posts: DocumentRepository
    media: DocumentRepository
    profiles: DocumentRepository
    journal: DocumentRepository
    enrichments: DocumentRepository

    def save(self, doc: Document) -> None:
        """Convenience method to save a document to the correct repository."""
        repo = self._get_repo(doc.doc_type)
        repo.save(doc)

    def _get_repo(self, doc_type: DocumentType) -> DocumentRepository:
        if doc_type == DocumentType.POST:
            return self.posts
        if doc_type == DocumentType.MEDIA:
            return self.media
        if doc_type == DocumentType.PROFILE:
            return self.profiles
        if doc_type == DocumentType.JOURNAL:
            return self.journal
        if doc_type in (DocumentType.ENRICHMENT_URL, DocumentType.ENRICHMENT_MEDIA):
            return self.enrichments

        # Fallback or error
        # Assuming posts is a safe default or raising error
        # For now, return posts to avoid crash if unexpected type
        logger.warning(f"Unknown document type {doc_type}, defaulting to posts repo")
        return self.posts

# Legacy aliases for backward compatibility if needed,
# but the instruction was to remove them.
# We intentionally do NOT export Service/Workspace/Collection.
