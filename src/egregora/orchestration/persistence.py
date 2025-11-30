"""Shared persistence utilities for agents and workers.

This module provides common logic for persisting generated content (banners, profiles)
to ensure consistency between synchronous tools and asynchronous workers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document, DocumentType

if TYPE_CHECKING:
    from egregora.data_primitives.protocols import OutputSink

logger = logging.getLogger(__name__)


def persist_banner_document(
    output_sink: OutputSink,
    document: Document,
) -> str:
    """Persist a banner document and return its web-accessible path.

    Args:
        output_sink: The output sink to persist to
        document: The banner document (type MEDIA)

    Returns:
        The canonical URL/path for the persisted banner

    """
    output_sink.persist(document)

    url_convention = output_sink.url_convention
    url_context = output_sink.url_context
    return url_convention.canonical_url(document, url_context)


def persist_profile_document(
    output_sink: OutputSink,
    author_uuid: str,
    content: str,
    source_window: str | None = None,
) -> str:
    """Create and persist a profile document.

    Args:
        output_sink: The output sink to persist to
        author_uuid: The author's UUID
        content: The profile content (markdown)
        source_window: Optional window label source

    Returns:
        The document ID of the saved profile

    """
    doc = Document(
        content=content,
        type=DocumentType.PROFILE,
        metadata={"uuid": author_uuid},
        source_window=source_window,
    )
    output_sink.persist(doc)
    logger.info("Saved profile for %s (doc_id: %s)", author_uuid, doc.document_id)
    return doc.document_id
