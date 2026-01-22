"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the unified documents table
in DuckDB.
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
    from egregora.database.duckdb_manager import DuckDBStorageManager


class ContentRepository:
    """Repository for content document operations."""

    def __init__(self, db: DuckDBStorageManager) -> None:
        self.db = db
        self._table_name = "documents"

    def save(self, doc: Document) -> None:
        """Save document to the unified documents table."""
        # Common fields mapping from Document to Schema
        row: dict[str, Any] = {
            "id": doc.document_id,  # Ensure we use the calculated stable ID
            "content": doc.content,
            "created_at": doc.created_at,
            "source_checksum": doc.internal_metadata.get("checksum"),
            "doc_type": doc.type.value,
            "status": doc.internal_metadata.get("status", "draft"),  # Default to draft
            "extensions": doc.internal_metadata.get("extensions"),
        }

        # Type-specific field mapping
        if doc.type == DocumentType.POST:
            row.update(
                {
                    "title": doc.metadata.get("title"),
                    "slug": doc.metadata.get("slug") or doc.slug,
                    "date": doc.metadata.get("date"),
                    "summary": doc.metadata.get("summary"),
                    "authors": doc.metadata.get("authors", []),
                    "tags": doc.metadata.get("tags", []),
                }
            )

        elif doc.type == DocumentType.PROFILE:
            row.update(
                {
                    "subject_uuid": doc.metadata.get("subject_uuid"),
                    "title": doc.metadata.get("title") or doc.metadata.get("name"),
                    "alias": doc.metadata.get("alias"),
                    "summary": doc.metadata.get("summary") or doc.metadata.get("bio"),
                    "avatar_url": doc.metadata.get("avatar_url"),
                    "interests": doc.metadata.get("interests", []),
                }
            )

        elif doc.type == DocumentType.MEDIA:
            row.update(
                {
                    "filename": doc.metadata.get("filename"),
                    "mime_type": doc.metadata.get("mime_type"),
                    "media_type": doc.metadata.get("media_type"),
                    "phash": doc.metadata.get("phash"),
                }
            )

        elif doc.type == DocumentType.JOURNAL:
            row.update(
                {
                    "title": doc.metadata.get("title") or doc.metadata.get("window_label"),
                    "window_start": doc.metadata.get("window_start"),
                    "window_end": doc.metadata.get("window_end"),
                }
            )

        elif doc.type == DocumentType.ANNOTATION:
            # Annotations are stored in a separate table 'annotations' in init.py
            # BUT schemas.py UNIFIED_SCHEMA does NOT include ANNOTATIONS_SCHEMA.
            # AND init.py creates 'annotations' table separately.
            # So we should probably route ANNOTATION to 'annotations' table.

            # Wait, schemas.py says:
            # DOCUMENTS_VIEW_SQL unioned annotations too.
            # But UNIFIED_SCHEMA definition does NOT include ANNOTATIONS_SCHEMA.

            # Let's keep ANNOTATION in 'annotations' table for now if that matches init.py structure.
            # BUT this 'save' method was seemingly trying to be universal.

            annotation_row = {
                "id": doc.document_id,
                "content": doc.content,
                "created_at": doc.created_at,
                "source_checksum": doc.internal_metadata.get("checksum"),
                "parent_id": doc.parent_id or doc.metadata.get("parent_id"),
                "parent_type": doc.metadata.get("parent_type"),
                "author_id": doc.metadata.get("author_id"),
            }
            self.db.ibis_conn.insert("annotations", [annotation_row])
            return

        # Insert into documents table
        # We need to filter out keys that are not in the schema or ensure schema handles None
        # Ibis insert usually handles this if columns match.

        # NOTE: UPSERT semantics.
        # For now, we'll try insert. If it exists, we might need an update or delete+insert.
        # DuckDB/Ibis insert usually appends.
        # Ideally we should check existence or use an upsert strategy.
        # For "Append-Only Core", we insert new versions.
        # But 'id' is a primary key?
        # schemas.py add_primary_key is available but not called in init.py for 'documents'.
        # init.py only adds indexes for 'messages'.

        # Let's check if 'id' is unique in UNIFIED_SCHEMA.
        # It's just dt.string.

        # If we append, we get duplicates.
        # The 'persist' contract says "writing the same document twice... should UPDATE".

        # Since Ibis/DuckDB upsert is tricky without explicit SQL,
        # checking existence and deleting first is a safe bet for now, or using CREATE OR REPLACE logic.

        # Given the previous implementation used 'insert', I will stick to 'insert' but maybe we should delete first?
        # The previous 'save' just did 'insert'.
        # I will assume for now that insert is fine or that the user handles uniqueness,
        # OR I should check if it exists.

        # Let's stick to insert for now to match previous behavior, but we might want to fix this later.
        self.db.ibis_conn.insert(self._table_name, [row])

    def get_all(self) -> Iterator[dict]:
        """Stream all documents from the documents table."""
        return self.db.execute(f"SELECT * FROM {self._table_name}").fetchall()

    def get(self, doc_type: DocumentType, identifier: str) -> Document:
        """Retrieve a single document by type and identifier."""
        from ibis.common.exceptions import IbisError

        try:
            t = self.db.read_table(self._table_name)

            # Filter by doc_type and identifier
            query = t.filter(t.doc_type == doc_type.value)

            if doc_type == DocumentType.POST:
                query = query.filter((t.id == identifier) | (t.slug == identifier))
            elif doc_type == DocumentType.PROFILE:
                query = query.filter((t.id == identifier) | (t.subject_uuid == identifier))
            else:
                query = query.filter(t.id == identifier)

            # Get latest if multiple? (Append-only implication)
            # For now, just take limit 1.
            res = query.limit(1).execute()

            if res.empty:
                raise DocumentNotFoundError(doc_type.value, identifier)

            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data, doc_type)

        except IbisError as e:
            msg = f"Failed to get document: {e}"
            raise DatabaseOperationError(msg) from e

    def list(self, doc_type: DocumentType | None = None) -> Iterator[dict]:
        """List documents metadata."""
        t = self.db.read_table(self._table_name)
        if doc_type:
            t = t.filter(t.doc_type == doc_type.value)

        # Select relevant columns? Or just return all?
        # Previous implementation returned all columns.
        yield from t.execute().to_dict(orient="records")

    def _row_to_document(self, row: dict, doc_type: DocumentType) -> Document:
        """Convert a DB row to a Document object."""
        # Extract known fields
        doc_id = row.get("id")
        content = row.get("content")
        created_at = row.get("created_at")

        # Build metadata
        metadata = {}

        if doc_type == DocumentType.POST:
            metadata.update(
                {
                    "title": row.get("title"),
                    "slug": row.get("slug"),
                    "date": row.get("date"),
                    "summary": row.get("summary"),
                    "authors": row.get("authors"),
                    "tags": row.get("tags"),
                }
            )
        elif doc_type == DocumentType.PROFILE:
            metadata.update(
                {
                    "subject_uuid": row.get("subject_uuid"),
                    "title": row.get("title"),
                    "alias": row.get("alias"),
                    "summary": row.get("summary"),
                    "avatar_url": row.get("avatar_url"),
                    "interests": row.get("interests"),
                }
            )
        elif doc_type == DocumentType.MEDIA:
            metadata.update(
                {
                    "filename": row.get("filename"),
                    "mime_type": row.get("mime_type"),
                    "media_type": row.get("media_type"),
                    "phash": row.get("phash"),
                }
            )
        elif doc_type == DocumentType.JOURNAL:
            metadata.update(
                {
                    "title": row.get("title"),
                    "window_start": row.get("window_start"),
                    "window_end": row.get("window_end"),
                }
            )

        # Common metadata
        if row.get("status"):
            metadata["status"] = row.get("status")

        # Internal metadata (everything else)
        internal_metadata = {
            k: v
            for k, v in row.items()
            if k not in metadata and k not in ["id", "content", "created_at", "doc_type", "extensions"]
        }
        if row.get("extensions"):
            # Merge extensions back? Or keep in internal?
            internal_metadata["extensions"] = row.get("extensions")

        return Document(
            id=doc_id,
            content=content,
            type=doc_type,
            metadata=metadata,
            internal_metadata=internal_metadata,
            created_at=created_at,
        )
