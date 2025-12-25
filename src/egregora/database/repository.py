"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the correct type-specific
tables in DuckDB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from ibis.common.exceptions import IbisError

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.utils import quote_identifier

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
            "id": doc.document_id,
            "content": doc.content if isinstance(doc.content, str) else None,
            "created_at": doc.created_at,
            "source_checksum": doc.metadata.get("checksum"),
        }

        if doc.type == DocumentType.POST:
            # Post specific fields
            row.update(
                {
                    "title": doc.metadata.get("title"),
                    "slug": doc.metadata.get("slug"),
                    "date": doc.metadata.get("date"),
                    "summary": doc.metadata.get("summary"),
                    "authors": doc.metadata.get("authors", []),
                    "tags": doc.metadata.get("tags", []),
                    "status": doc.metadata.get("status", "published"),
                }
            )
            self.db.ibis_conn.insert("posts", [row])

        elif doc.type == DocumentType.PROFILE:
            # Profile specific fields
            row.update(
                {
                    "subject_uuid": doc.metadata.get("subject_uuid"),
                    "title": doc.metadata.get("title"),  # Was 'name'
                    "alias": doc.metadata.get("alias"),
                    "summary": doc.metadata.get("summary"),  # Was 'bio'
                    "avatar_url": doc.metadata.get("avatar_url"),
                    "interests": doc.metadata.get("interests", []),
                }
            )
            self.db.ibis_conn.insert("profiles", [row])

        elif doc.type == DocumentType.MEDIA:
            row.update(
                {
                    "filename": doc.metadata.get("filename"),
                    "mime_type": doc.metadata.get("mime_type"),
                    "media_type": doc.metadata.get("media_type"),
                    "phash": doc.metadata.get("phash"),
                }
            )
            self.db.ibis_conn.insert("media", [row])

        elif doc.type == DocumentType.JOURNAL:
            row.update(
                {
                    "title": doc.metadata.get("title"),  # Was 'window_label'
                    "window_start": doc.metadata.get("window_start"),
                    "window_end": doc.metadata.get("window_end"),
                }
            )
            self.db.ibis_conn.insert("journals", [row])

        elif doc.type == DocumentType.ANNOTATION:
            row.update(
                {
                    "parent_id": doc.metadata.get("parent_id"),
                    "parent_type": doc.metadata.get("parent_type"),
                    "author_id": doc.metadata.get("author_id"),
                    "category": doc.metadata.get("category"),
                    "tags": doc.metadata.get("tags", []),
                }
            )
            self.db.ibis_conn.insert("annotations", [row])
        else:
            # Fallback for unsupported types - perhaps log warning
            pass

    def get_all(self) -> Iterator[dict]:
        """Stream all documents via the unified view."""
        return self.db.execute("SELECT * FROM documents_view").fetchall()

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by type and identifier."""
        table_name = self._get_table_for_type(doc_type)
        if not table_name:
            return None

        # Determine lookup column based on type
        if doc_type == DocumentType.POST:
            # Posts might be looked up by slug or ID. The identifier here is usually the slug for posts.
            # But OutputSink.read_document typically uses the 'storage identifier'.
            # Let's assume ID first, then fallback or specific logic.
            # For now, let's query by ID matching identifier.
            pass
            # Or slug? 'read_document' contract says "primary identifier".
            # MkDocs adapter uses relative path.
            # Here we use the ID stored in the DB.

        quoted_table = quote_identifier(table_name)
        # Using parameterized query for safety
        row = self.db.execute_query_single(f"SELECT * FROM {quoted_table} WHERE id = ?", [identifier])

        if not row:
            # Try slug if POST/PROFILE
            if doc_type == DocumentType.POST:
                row = self.db.execute_query_single(
                    f"SELECT * FROM {quoted_table} WHERE slug = ?", [identifier]
                )
            elif doc_type == DocumentType.PROFILE:
                # Profile lookup might be by subject_uuid
                row = self.db.execute_query_single(
                    f"SELECT * FROM {quoted_table} WHERE subject_uuid = ?", [identifier]
                )

        if not row:
            return None

        # Convert row tuple to dict using column names
        self.db.get_table_columns(table_name)
        # Sort cols to match table schema order? get_table_columns returns set.
        # We need ordered columns. PRAGMA table_info gives order.
        # This is getting complicated with raw SQL.
        # Better to use Ibis to fetch single row if possible, or assume column order.
        # But for robustness, let's just fetch as dict using column names from ibis schema.

        # Simplified: Use Ibis
        try:
            t = self.db.read_table(table_name)
            # Filter
            if doc_type == DocumentType.POST:
                res = t.filter((t.id == identifier) | (t.slug == identifier)).limit(1).execute()
            elif doc_type == DocumentType.PROFILE:
                res = t.filter((t.id == identifier) | (t.subject_uuid == identifier)).limit(1).execute()
            else:
                res = t.filter(t.id == identifier).limit(1).execute()

            if res.empty:
                return None

            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data, doc_type)

        except (IbisError, IndexError):
            return None

    def list(self, doc_type: DocumentType | None = None) -> Iterator[dict]:
        """List documents metadata."""
        if doc_type:
            table_name = self._get_table_for_type(doc_type)
            if not table_name:
                return
            t = self.db.read_table(table_name)
            # Select relevant columns for metadata
            # We need to return iterator of dicts
            yield from t.execute().to_dict(orient="records")
        else:
            # Use Ibis to read the view as a table for consistent dict output
            try:
                t = self.db.read_table("documents_view")
                yield from t.execute().to_dict(orient="records")
            except IbisError:
                # Fallback if view not registered in ibis cache or other issue
                # Manually map columns for robustness
                rows = self.db.execute("SELECT * FROM documents_view").fetchall()
                # columns: id, type, content, created_at, title, slug, subject_uuid
                cols = ["id", "type", "content", "created_at", "title", "slug", "subject_uuid"]
                for row in rows:
                    yield dict(zip(cols, row, strict=False))

    def _get_table_for_type(self, doc_type: DocumentType) -> str | None:
        mapping = {
            DocumentType.POST: "posts",
            DocumentType.PROFILE: "profiles",
            DocumentType.MEDIA: "media",
            DocumentType.JOURNAL: "journals",
            DocumentType.ANNOTATION: "annotations",
        }
        return mapping.get(doc_type)

    def _row_to_document(self, row: dict, doc_type: DocumentType) -> Document:
        """Convert a DB row to a Document object."""
        # Reconstruct Document metadata from row columns
        metadata = {}
        metadata = {k: v for k, v in row.items() if k not in ["content", "id", "created_at"]}

        return Document(
            id=row.get("id"),
            content=row.get("content") or "",
            type=doc_type,
            metadata=metadata,
            created_at=row.get("created_at"),
        )
