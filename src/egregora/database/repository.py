"""Data access layer for content (Posts, Profiles, Media, Journals).

This repository handles routing document operations to the correct type-specific
tables in DuckDB.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from ibis.common.exceptions import IbisError

# V2 document for backward compatibility
from egregora.data_primitives.document import Document, DocumentType
# V3 document for forward compatibility
from egregora_v3.core.types import Document as V3Document
from egregora_v3.core.types import DocumentType as V3DocumentType

from egregora.database.utils import quote_identifier

if TYPE_CHECKING:
    from egregora.database.duckdb_manager import DuckDBStorageManager


class ContentRepository:
    """Repository for content document operations."""

    def __init__(self, db: DuckDBStorageManager) -> None:
        self.db = db

    def save(self, doc: Document | V3Document) -> None:
        """Route document to correct table based on type."""
        is_v3 = isinstance(doc, V3Document)

        if is_v3:
            # Handle V3 Document
            doc_type = doc.doc_type
            row = {
                "id": doc.id,
                "content": doc.content if isinstance(doc.content, str) else None,
                "created_at": doc.updated,
                "source_checksum": doc.internal_metadata.get("checksum"),
            }
            if doc_type == V3DocumentType.POST:
                row.update({
                    "title": doc.title, "slug": doc.slug, "date": doc.published or doc.updated,
                    "summary": doc.summary, "authors": [a.name for a in doc.authors],
                    "tags": [c.term for c in doc.categories], "status": doc.status.value,
                })
            elif doc_type == V3DocumentType.PROFILE:
                row.update({
                    "subject_uuid": doc.internal_metadata.get("subject_uuid"), "title": doc.title,
                    "alias": doc.internal_metadata.get("alias"), "summary": doc.summary,
                    "avatar_url": doc.internal_metadata.get("avatar_url"),
                    "interests": doc.internal_metadata.get("interests", []),
                })
            elif doc_type == V3DocumentType.MEDIA:
                row.update({
                    "filename": doc.internal_metadata.get("filename"),
                    "mime_type": doc.internal_metadata.get("mime_type"),
                    "media_type": doc.internal_metadata.get("media_type"),
                    "phash": doc.internal_metadata.get("phash"),
                })
            elif doc_type == V3DocumentType.ENRICHMENT:
                parent = doc.in_reply_to
                row.update({
                    "parent_id": parent.ref if parent else None,
                    "parent_type": parent.type if parent else None,
                    "author_id": doc.authors[0].uri if doc.authors else None,
                    "category": doc.categories[0].term if doc.categories else None,
                    "tags": [c.term for c in doc.categories],
                })
            else:
                return  # Skip unsupported types
        else:
            # Handle V2 Document
            doc_type = doc.type
            row = {
                "id": doc.document_id,
                "content": doc.content if isinstance(doc.content, str) else None,
                "created_at": doc.created_at,
                "source_checksum": doc.metadata.get("checksum"),
            }
            if doc_type == DocumentType.POST:
                row.update({
                    "title": doc.metadata.get("title"), "slug": doc.metadata.get("slug"),
                    "date": doc.metadata.get("date"), "summary": doc.metadata.get("summary"),
                    "authors": doc.metadata.get("authors", []), "tags": doc.metadata.get("tags", []),
                    "status": doc.metadata.get("status", "published"),
                })
            elif doc_type == DocumentType.PROFILE:
                row.update({
                    "subject_uuid": doc.metadata.get("subject_uuid"), "title": doc.metadata.get("title"),
                    "alias": doc.metadata.get("alias"), "summary": doc.metadata.get("summary"),
                    "avatar_url": doc.metadata.get("avatar_url"), "interests": doc.metadata.get("interests", []),
                })
            elif doc_type == DocumentType.MEDIA:
                row.update({
                    "filename": doc.metadata.get("filename"), "mime_type": doc.metadata.get("mime_type"),
                    "media_type": doc.metadata.get("media_type"), "phash": doc.metadata.get("phash"),
                })
            elif doc_type == DocumentType.JOURNAL:
                row.update({
                    "title": doc.metadata.get("title"), "window_start": doc.metadata.get("window_start"),
                    "window_end": doc.metadata.get("window_end"),
                })
            elif doc_type == DocumentType.ANNOTATION:
                row.update({
                    "parent_id": doc.metadata.get("parent_id"), "parent_type": doc.metadata.get("parent_type"),
                    "author_id": doc.metadata.get("author_id"), "category": doc.metadata.get("category"),
                    "tags": doc.metadata.get("tags", []),
                })
            else:
                return

        table_name = self._get_table_for_type(doc_type)
        if table_name:
            self.db.ibis_conn.insert(table_name, [row])

    def get_all(self) -> Iterator[dict]:
        """Stream all documents via the unified view."""
        return self.db.execute("SELECT * FROM documents_view").fetchall()

    def get(self, doc_type: DocumentType, identifier: str) -> Document | None:
        """Retrieve a single document by type and identifier."""
        table_name = self._get_table_for_type(doc_type)
        if not table_name: return None
        try:
            t = self.db.read_table(table_name)
            if doc_type == DocumentType.POST:
                res = t.filter((t.id == identifier) | (t.slug == identifier)).limit(1).execute()
            elif doc_type == DocumentType.PROFILE:
                res = t.filter((t.id == identifier) | (t.subject_uuid == identifier)).limit(1).execute()
            else:
                res = t.filter(t.id == identifier).limit(1).execute()
            if res.empty: return None
            data = res.to_dict(orient="records")[0]
            return self._row_to_document(data, doc_type)
        except (IbisError, IndexError):
            return None

    def list(self, doc_type: DocumentType | None = None) -> Iterator[dict]:
        """List documents metadata."""
        if doc_type:
            table_name = self._get_table_for_type(doc_type)
            if not table_name: return
            t = self.db.read_table(table_name)
            yield from t.execute().to_dict(orient="records")
        else:
            try:
                t = self.db.read_table("documents_view")
                yield from t.execute().to_dict(orient="records")
            except IbisError:
                rows = self.db.execute("SELECT * FROM documents_view").fetchall()
                cols = ["id", "type", "content", "created_at", "title", "slug", "subject_uuid"]
                for row in rows:
                    yield dict(zip(cols, row, strict=False))

    def _get_table_for_type(self, doc_type: DocumentType | V3DocumentType) -> str | None:
        """Get table name for a given DocumentType enum member."""
        doc_type_str = doc_type.value
        mapping = {
            "post": "posts", "profile": "profiles", "media": "media",
            "journal": "journals", "annotation": "annotations", "enrichment": "annotations",
        }
        return mapping.get(doc_type_str)

    def _row_to_document(self, row: dict, doc_type: DocumentType) -> Document:
        """Convert a DB row to a V2 Document object."""
        metadata = {k: v for k, v in row.items() if k not in ["content", "id", "created_at"]}
        return Document(
            id=row.get("id"), content=row.get("content") or "", type=doc_type,
            metadata=metadata, created_at=row.get("created_at"),
        )
