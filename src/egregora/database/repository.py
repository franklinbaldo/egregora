"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the correct type-specific
tables in DuckDB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.exceptions import (
    DatabaseOperationError,
    DocumentNotFoundError,
    UnsupportedDocumentTypeError,
)

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class ContentRepository:
    """Repository for content document operations."""

    def __init__(self, db: DuckDBStorageManager) -> None:
        self.db = db

    def save(self, doc: Document) -> None:
        """Route document to correct table based on type."""
        # Common fields mapping from Document to Schema
        row = {
            "id": str(doc.id) if doc.id else None,
            "content": doc.content,
            "created_at": doc.updated,  # Using updated as created_at/insertion time
            "source_checksum": doc.internal_metadata.get("checksum"),
        }

        if doc.doc_type == DocumentType.POST:
            # Post specific fields
            row.update(
                {
                    "title": doc.title,
                    "slug": doc.internal_metadata.get("slug"),
                    "date": doc.internal_metadata.get("date"),
                    "summary": doc.summary,
                    # "authors": [str(a.id) for a in doc.authors],
                    # "tags": [c.term for c in doc.categories],
                    "status": doc.status,
                }
            )
            self.db.ibis_conn.insert("posts", [row])

        elif doc.doc_type == DocumentType.PROFILE:
            # Profile specific fields
            row.update(
                {
                    "subject_uuid": doc.internal_metadata.get("subject_uuid"),
                    "title": doc.title,  # Was 'name'
                    "alias": doc.internal_metadata.get("alias"),
                    "summary": doc.summary,  # Was 'bio'
                    "avatar_url": doc.internal_metadata.get("avatar_url"),
                    "interests": doc.internal_metadata.get("interests", []),
                }
            )
            self.db.ibis_conn.insert("profiles", [row])

        elif doc.doc_type == DocumentType.MEDIA:
            row.update(
                {
                    "filename": doc.internal_metadata.get("filename"),
                    "mime_type": doc.content_type,
                    "media_type": doc.internal_metadata.get("media_type"),
                    "phash": doc.internal_metadata.get("phash"),
                }
            )
            self.db.ibis_conn.insert("media", [row])

        elif doc.doc_type == DocumentType.JOURNAL:
            row.update(
                {
                    "title": doc.title,  # Was 'window_label'
                    "window_start": doc.internal_metadata.get("window_start"),
                    "window_end": doc.internal_metadata.get("window_end"),
                }
            )
            self.db.ibis_conn.insert("journals", [row])

        elif doc.doc_type == DocumentType.ANNOTATION:
            row.update(
                {
                    "parent_id": doc.internal_metadata.get("parent_id"),
                    "parent_type": doc.internal_metadata.get("parent_type"),
                    "author_id": doc.internal_metadata.get("author_id"),
                }
            )
            self.db.ibis_conn.insert("annotations", [row])
        else:
            # Fallback for unsupported types - perhaps log warning
            pass

    def get_all(self) -> Iterator[dict]:
        """Stream all documents via the unified view."""
        return self.db.execute("SELECT * FROM documents_view").fetch_arrow_table().to_pylist()

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve a single document by type and identifier."""
        table_name = self._get_table_for_type(doc_type)

        from ibis.common.exceptions import IbisError

        try:
            t = self.db.read_table(table_name)
            # Filter based on document type's potential identifiers
            if doc_type == DocumentType.POST:
                res = t.filter((t.id == identifier) | (t.slug == identifier)).limit(1).execute()
            elif doc_type == DocumentType.PROFILE:
                res = t.filter((t.id == identifier) | (t.subject_uuid == identifier)).limit(1).execute()
            else:
                res = t.filter(t.id == identifier).limit(1).execute()

            if res.empty:
                raise DocumentNotFoundError(doc_type.value, identifier)

            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data, doc_type)

        except IbisError as e:
            msg = f"Failed to get document: {e}"
            raise DatabaseOperationError(msg) from e

    def list(self, doc_type: DocumentType | None = None) -> Iterator[dict]:
        """List documents metadata."""
        if doc_type:
            table_name = self._get_table_for_type(doc_type)
            t = self.db.read_table(table_name)
            # Use fetch_arrow_table().to_pylist() for efficient streaming
            yield from t.execute().fetch_arrow_table().to_pylist()
        else:
            # Use Ibis to read the view as a table for consistent dict output
            from ibis.common.exceptions import IbisError

            try:
                t = self.db.read_table("documents_view")
                yield from t.execute().fetch_arrow_table().to_pylist()
            except IbisError:
                # Fallback if view not registered in ibis cache or other issue
                # Manually map columns for robustness
                relation = self.db.execute("SELECT * FROM documents_view")
                cols = [desc[0] for desc in relation.description]
                for row in relation.fetchall():
                    yield dict(zip(cols, row, strict=False))

    def _get_table_for_type(self, doc_type: DocumentType) -> str:
        mapping = {
            DocumentType.POST: "posts",
            DocumentType.PROFILE: "profiles",
            DocumentType.MEDIA: "media",
            DocumentType.JOURNAL: "journals",
            DocumentType.ANNOTATION: "annotations",
        }
        table = mapping.get(doc_type)
        if not table:
            raise UnsupportedDocumentTypeError(str(doc_type))
        return table

    def _row_to_document(self, row: dict, doc_type: DocumentType) -> Document:
        """Convert a DB row to a Document object."""
        # Reconstruct Document
        # internal_metadata needs to be populated from specific columns
        internal_metadata = {
            k: v
            for k, v in row.items()
            if k not in ["content", "id", "created_at", "updated", "title", "summary"]
        }

        # Authors list reconstruction
        # if row.get("authors"):
        #     # Assuming row['authors'] is list of strings (UUIDs)
        #     authors = [Author(id=uid, name="") for uid in row["authors"]]

        # if row.get("tags"):
        #     categories = [Category(term=tag) for tag in row["tags"]]

        return Document(
            id=row.get("id"),
            title=row.get("title"),
            content=row.get("content"),
            updated=row.get("created_at"),  # Map created_at back to updated?
            summary=row.get("summary"),
            # authors=authors,
            # categories=categories,
            doc_type=doc_type,
            internal_metadata=internal_metadata,
        )
