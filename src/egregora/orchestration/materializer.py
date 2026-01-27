"""Materialization logic to sync ContentRepository to Filesystem.

This module reads from the database sink and writes to the filesystem sink (MkDocsAdapter),
bridging the "Database Source of Truth" with the "Static Site Artifact".
"""

import logging
from typing import TYPE_CHECKING

from egregora.data_primitives.document import DocumentType, OutputSink
from egregora.output_sinks.exceptions import DocumentNotFoundError

if TYPE_CHECKING:
    from egregora.output_sinks.mkdocs.adapter import MkDocsAdapter

logger = logging.getLogger(__name__)


def materialize_site(source: OutputSink, destination: "MkDocsAdapter") -> None:
    """Sync all documents from DB to Filesystem."""
    logger.info("🧱 [bold cyan]Materializing site from database...[/]")

    count = 0
    # Iterate all types
    for doc_type in [
        DocumentType.POST,
        DocumentType.PROFILE,
        DocumentType.JOURNAL,
        DocumentType.MEDIA,
        DocumentType.ANNOTATION,
    ]:
        # We need a robust iterator that yields full Document objects
        # DbOutputSink.list() yields metadata. We can use that to fetch docs.

        for meta in source.list(doc_type):
            try:
                doc = source.get(doc_type, meta.identifier)
                destination.persist(doc)
                count += 1
            except DocumentNotFoundError:
                logger.warning(
                    "Skipping materialization of missing document: type=%s, id=%s",
                    doc_type.value,
                    meta.identifier,
                )
                continue

    logger.info("✅ [green]Materialized %d documents to filesystem.[/]", count)
