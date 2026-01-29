"""Database Output Sink.

This sink implements the OutputSink protocol but persists documents to the
central ContentRepository (DuckDB) instead of the filesystem.
"""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from typing import Any

from egregora.data_primitives.document import (
    Document,
    DocumentMetadata,
    DocumentType,
    OutputSink,
    UrlContext,
    UrlConvention,
)
from egregora.database.repository import ContentRepository
from egregora.output_sinks.conventions import StandardUrlConvention
from egregora.output_sinks.exceptions import (
    DocumentIterationError,
    DocumentNotFoundError,
)


class DbOutputSink(OutputSink):
    """OutputSink implementation that persists to DuckDB via ContentRepository."""

    def __init__(self, repository: ContentRepository, url_context: UrlContext | None = None) -> None:
        self.repository = repository
        self._url_convention = StandardUrlConvention()
        self._ctx = url_context or UrlContext()

    @property
    def url_convention(self) -> UrlConvention:
        return self._url_convention

    @property
    def url_context(self) -> UrlContext:
        return self._ctx

    def persist(self, document: Document) -> None:
        """Persist document to the database repository."""
        self.repository.save(document)

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve document from database."""
        document = self.repository.get(doc_type, identifier)
        if document is None:
            raise DocumentNotFoundError(doc_type.value, identifier)
        return document

    def list(self, doc_type: DocumentType | None = None) -> Iterator[DocumentMetadata]:
        """List documents from database as metadata."""
        # ContentRepository.list returns dicts. We convert to DocumentMetadata.
        for row in self.repository.list(doc_type):
            # Identifier strategy: Use ID as storage identifier for DB
            identifier = str(row.get("id"))

            # Map doc_type string back to Enum if needed, or rely on caller filter
            # repository.list(doc_type) ensures we get the right type.
            # If doc_type is None, we need to infer from view 'type' column.
            dtype = doc_type
            if dtype is None and "type" in row:
                try:
                    # simplistic mapping from string "post" -> DocumentType.POST
                    # This relies on view column 'type' matching convention
                    type_str = row["type"].upper()
                    if type_str == "POST":
                        dtype = DocumentType.POST
                    elif type_str == "PROFILE":
                        dtype = DocumentType.PROFILE
                    elif type_str == "JOURNAL":
                        dtype = DocumentType.JOURNAL
                    elif type_str == "MEDIA":
                        dtype = DocumentType.MEDIA
                    elif type_str == "ANNOTATION":
                        dtype = DocumentType.ANNOTATION
                except (KeyError, AttributeError):
                    pass

            yield DocumentMetadata(
                identifier=identifier,
                doc_type=dtype,
                metadata=row,  # Pass full row as metadata
            )

    def documents(self) -> Iterator[Document]:
        """Iterate all documents."""
        # Use repository.get_all which streams from view
        # We assume get_all returns rows that allow us to fetch/reconstruct.
        # However, for robustness and since get_all returns generic view rows (subset of columns),
        # we should iterate per-type via list() which returns metadata, then fetch full docs.
        # This is slower but safer for materialization.

        # Iterate through all known types in the sink
        known_types = [
            DocumentType.POST,
            DocumentType.PROFILE,
            DocumentType.JOURNAL,
            DocumentType.MEDIA,
            DocumentType.ANNOTATION,
        ]

        for dtype in known_types:
            for meta in self.list(dtype):
                try:
                    doc = self.get(dtype, meta.identifier)
                    yield doc
                except DocumentNotFoundError as e:
                    raise DocumentIterationError(doc_type=e.doc_type, identifier=e.identifier) from e

    def get_format_instructions(self) -> str:
        return "Database persistence mode."

    def finalize_window(
        self,
        window_label: str,
        _posts_created: builtins.list[str],
        profiles_updated: builtins.list[str],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass
