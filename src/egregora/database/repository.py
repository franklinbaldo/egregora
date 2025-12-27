"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the correct type-specific
tables in DuckDB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.exceptions import (
    DocumentNotFoundError,
    RepositoryQueryError,
    UnsupportedDocumentTypeError,
)

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class ContentRepository:
    """Repository for content document operations."""

    def __init__(self, db: DuckDBStorageManager) -> None:
        self.db = db

    def _get_table_for_type(self, doc_type: DocumentType) -> str:
        """Return the table name for a given DocumentType, or raise an exception."""
        mapping = {
            DocumentType.POST: "posts",
            DocumentType.PROFILE: "profiles",
            DocumentType.MEDIA: "media",
            DocumentType.JOURNAL: "journals",
            DocumentType.ANNOTATION: "annotations",
        }
        table = mapping.get(doc_type)
        if not table:
            type_name = doc_type.name if hasattr(doc_type, "name") else str(doc_type)
            raise UnsupportedDocumentTypeError(type_name)
        return table

    def save(self, doc: Document) -> None:
        """Route document to correct table based on type."""
        table_name = self._get_table_for_type(doc.type)
        row = {
            "id": doc.document_id,
            "content": doc.content if isinstance(doc.content, str) else None,
            "created_at": doc.created_at,
            "source_checksum": doc.metadata.get("checksum"),
        }
        specific_fields = {}
        if doc.type == DocumentType.POST:
            specific_fields = {
                "title": doc.metadata.get("title"),
                "slug": doc.metadata.get("slug"),
                "date": doc.metadata.get("date"),
                "summary": doc.metadata.get("summary"),
                "authors": doc.metadata.get("authors", []),
                "tags": doc.metadata.get("tags", []),
                "status": doc.metadata.get("status", "published"),
            }
        elif doc.type == DocumentType.PROFILE:
            specific_fields = {
                "subject_uuid": doc.metadata.get("subject_uuid"),
                "title": doc.metadata.get("title"),
                "alias": doc.metadata.get("alias"),
                "summary": doc.metadata.get("summary"),
                "avatar_url": doc.metadata.get("avatar_url"),
                "interests": doc.metadata.get("interests", []),
            }
        elif doc.type == DocumentType.MEDIA:
            specific_fields = {
                "filename": doc.metadata.get("filename"),
                "mime_type": doc.metadata.get("mime_type"),
                "media_type": doc.metadata.get("media_type"),
                "phash": doc.metadata.get("phash"),
            }
        elif doc.type == DocumentType.JOURNAL:
            specific_fields = {
                "title": doc.metadata.get("title"),
                "window_start": doc.metadata.get("window_start"),
                "window_end": doc.metadata.get("window_end"),
            }
        elif doc.type == DocumentType.ANNOTATION:
            specific_fields = {
                "parent_id": doc.metadata.get("parent_id"),
                "parent_type": doc.metadata.get("parent_type"),
                "author_id": doc.metadata.get("author_id"),
                "category": doc.metadata.get("category"),
                "tags": doc.metadata.get("tags", []),
            }

        row.update(specific_fields)
        self.db.ibis_conn.insert(table_name, [row])

    def get_all(self) -> Iterator[dict]:
        """Stream all documents via the unified view."""
        return self.db.execute("SELECT * FROM documents_view").fetchall()

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve a single document by type and identifier."""
        table_name = self._get_table_for_type(doc_type)
        try:
            t = self.db.read_table(table_name)
            if doc_type == DocumentType.POST:
                res = t.filter((t.id == identifier) | (t.slug == identifier)).limit(1).execute()
            elif doc_type == DocumentType.PROFILE:
                res = t.filter((t.id == identifier) | (t.subject_uuid == identifier)).limit(1).execute()
            else:
                res = t.filter(t.id == identifier).limit(1).execute()
            if res.empty:
                raise DocumentNotFoundError(doc_type.name, identifier)
            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data, doc_type)
        except IbisError as e:
            msg = f"Query failed for {doc_type.name} '{identifier}'"
            raise RepositoryQueryError(msg) from e
        except IndexError as e:
            raise DocumentNotFoundError(doc_type.name, identifier) from e

    def list(self, doc_type: DocumentType) -> Iterator[Document]:
        """Lists all documents of a given type."""
        table_name = self._get_table_for_type(doc_type)
        try:
            table = self.db.read_table(table_name)
            for doc_dict in table.execute().to_dicts():
                yield self._row_to_document(doc_dict, doc_type)
        except (IbisError, IndexError) as e:
            msg = f"Failed to list documents of type {doc_type.name}"
            raise RepositoryQueryError(msg) from e

    def _row_to_document(self, row: dict, doc_type: DocumentType) -> Document:
        """Convert a DB row to a Document object."""
        metadata = {k: v for k, v in row.items() if k not in ["content", "id", "created_at"]}
        return Document(
            id=row.get("id"),
            content=row.get("content") or "",
            type=doc_type,
            metadata=metadata,
            created_at=row.get("created_at"),
        )
