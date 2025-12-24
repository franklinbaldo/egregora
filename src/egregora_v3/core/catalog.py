
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import DocumentType

if TYPE_CHECKING:
    from egregora_v3.core.types import Document

logger = logging.getLogger(__name__)


class ContentLibrary(BaseModel):
    """Facade for content repositories."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    posts: DocumentRepository
    media: DocumentRepository
    profiles: DocumentRepository
    journal: DocumentRepository
    enrichments: DocumentRepository

    @property
    def _repo_map(self) -> dict[DocumentType, DocumentRepository]:
        """Data over logic: Use a map for routing."""
        return {
            DocumentType.POST: self.posts,
            DocumentType.MEDIA: self.media,
            DocumentType.PROFILE: self.profiles,
            DocumentType.NOTE: self.journal,  # NOTE maps to journal
            DocumentType.ENRICHMENT: self.enrichments,
        }

    def save(self, doc: Document) -> None:
        """Convenience method to save a document to the correct repository."""
        repo = self._get_repo(doc.doc_type)
        repo.save(doc)

    def _get_repo(self, doc_type: DocumentType) -> DocumentRepository:
        """Get the repository for a given document type."""
        # Use the map with a safe fallback to the 'posts' repository.
        repo = self._repo_map.get(doc_type)
        if repo:
            return repo

        logger.warning("Unknown document type %s, defaulting to posts repo", doc_type)
        return self.posts
