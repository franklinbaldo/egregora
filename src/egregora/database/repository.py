"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the unified documents table in DuckDB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.exceptions import (
    DatabaseOperationError,
    DocumentNotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from egregora.database.duckdb_manager import DuckDBStorageManager


class ContentRepository:
    """Repository for content document operations."""

    def __init__(self, db: DuckDBStorageManager) -> None:
        self.db = db
        self._table_name = "documents"

    def save(self, doc: Document) -> None:
        """Save document to the unified documents table."""
        # 1. Base mapping (Common to all types)
        row: dict[str, Any] = {
            "id": doc.document_id,  # Use stable ID property
            "content": doc.content
            if isinstance(doc.content, str)
            else doc.content.decode("utf-8", errors="ignore"),
            "created_at": doc.created_at,
            "source_checksum": doc.internal_metadata.get("checksum"),
            "doc_type": doc.type.value,
            "status": doc.metadata.get("status", "published"),  # Default status if not provided
            "extensions": None,
        }

        # 2. Type-specific mapping
        if doc.type == DocumentType.POST:
            row.update(
                {
                    "title": doc.metadata.get("title"),
                    "slug": doc.slug,  # Use property that handles fallback
                    "date": doc.internal_metadata.get("date"),
                    "summary": doc.metadata.get("summary"),
                    "authors": doc.metadata.get("authors", []),
                    "tags": doc.metadata.get("tags", []),
                    "status": doc.metadata.get("status"),
                }
            )

        elif doc.type == DocumentType.PROFILE:
            row.update(
                {
                    "subject_uuid": doc.internal_metadata.get("subject_uuid")
                    or doc.document_id,  # Fallback to ID if needed
                    "title": doc.metadata.get("title") or doc.metadata.get("name"),
                    "alias": doc.internal_metadata.get("alias"),
                    "summary": doc.metadata.get("summary") or doc.metadata.get("bio"),
                    "avatar_url": doc.metadata.get("avatar_url"),
                    "interests": doc.metadata.get("interests", []),
                }
            )

        elif doc.type == DocumentType.MEDIA:
            row.update(
                {
                    "filename": doc.internal_metadata.get("filename"),
                    "mime_type": doc.internal_metadata.get("mime_type"),  # Was mime_type in schema
                    "media_type": doc.internal_metadata.get("media_type"),
                    "phash": doc.internal_metadata.get("phash"),
                }
            )

        elif doc.type == DocumentType.JOURNAL:
            row.update(
                {
                    "title": doc.metadata.get("title") or doc.metadata.get("window_label"),
                    "window_start": doc.internal_metadata.get("window_start"),
                    "window_end": doc.internal_metadata.get("window_end"),
                }
            )

        elif doc.type == DocumentType.ANNOTATION:
            pass

        try:
            self.db.replace_rows("documents", [row], by_keys={"id": row["id"]})
        except Exception as e:
            msg = f"Failed to save document {row['id']}: {e}"
            raise DatabaseOperationError(msg) from e

    def get_all(self) -> Iterator[Document]:
        """Stream all documents from the unified table."""
        try:
            t = self.db.read_table("documents")
            # Return Document objects, not dicts
            for row in t.execute().to_dict(orient="records"):
                yield self._row_to_document(row)
        except Exception as e:
            msg = f"Failed to get all documents: {e}"
            raise DatabaseOperationError(msg) from e

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve a single document by type and identifier."""
        try:
            t = self.db.read_table("documents")

            # Filter by ID and Type
            # Also support slug lookup for Posts?

            if doc_type == DocumentType.POST:
                # Try ID match first
                res = t.filter((t.doc_type == doc_type.value) & (t.id == identifier)).limit(1).execute()
                if res.empty:
                    # Try Slug match
                    res = t.filter((t.doc_type == doc_type.value) & (t.slug == identifier)).limit(1).execute()
            else:
                res = t.filter((t.doc_type == doc_type.value) & (t.id == identifier)).limit(1).execute()

            if res.empty:
                raise DocumentNotFoundError(doc_type.value, identifier)

            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data)
        except DocumentNotFoundError:
            raise
        except Exception as e:
            # Catch IbisError and others
            msg = f"Failed to get document: {e}"
            raise DatabaseOperationError(msg) from e

    def list(self, doc_type: DocumentType | None = None) -> Iterator[dict[str, Any]]:
        """List documents metadata."""
        try:
            t = self.db.read_table("documents")
            if doc_type:
                t = t.filter(t.doc_type == doc_type.value)

            yield from t.execute().to_dict(orient="records")
        except Exception as e:
            # Fallback or error?
            # Old code had fallback. New code assumes 'documents' exists.
            # If 'documents' table missing, it will raise TableNotFoundError which is fine.
            msg = f"Failed to list documents: {e}"
            raise DatabaseOperationError(msg) from e

    def _row_to_document(self, row: dict) -> Document:
        """Convert a DB row to a Document object."""
        doc_type_str = row.get("doc_type")
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            # Fallback or error?
            doc_type = DocumentType.POST  # Default? Or raise

        # Reconstruct metadata
        metadata = {
            "title": row.get("title"),
            "summary": row.get("summary"),
            "status": row.get("status"),
            "slug": row.get("slug"),
            "date": row.get("date"),
            "authors": row.get("authors"),
            "tags": row.get("tags"),
            "name": row.get("title"),  # Alias for Profile
            "bio": row.get("summary"),  # Alias for Profile
            "avatar_url": row.get("avatar_url"),
            "interests": row.get("interests"),
            "window_label": row.get("title"),  # Alias for Journal
        }

        # Filter None values to clean up metadata
        metadata = {k: v for k, v in metadata.items() if v is not None}

        internal_metadata = {
            "checksum": row.get("source_checksum"),
            "subject_uuid": row.get("subject_uuid"),
            "alias": row.get("alias"),
            "filename": row.get("filename"),
            "mime_type": row.get("mime_type"),
            "media_type": row.get("media_type"),
            "phash": row.get("phash"),
            "window_start": row.get("window_start"),
            "window_end": row.get("window_end"),
        }
        # Filter None values
        internal_metadata = {k: v for k, v in internal_metadata.items() if v is not None}

        # Populate metadata with fields that were extracted
        metadata = {}
        if "title" in row:
            metadata["title"] = row["title"]
        if "summary" in row:
            metadata["summary"] = row["summary"]
        if "status" in row:
            metadata["status"] = row["status"]
        if "mime_type" in row:
            metadata["mime_type"] = row["mime_type"]

        return Document(
            id=row.get("id"),
            content=row.get("content", ""),
            type=doc_type,
            metadata=metadata,
            internal_metadata=internal_metadata,
            created_at=row.get("created_at"),
        )
