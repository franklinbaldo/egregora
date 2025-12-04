"""DuckDB Implementation of the Document Repository.

Implements the single-table storage pattern defined in RFC 2025-11-28.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import ibis
import ibis.expr.datatypes as dt
from ibis.backends import BaseBackend

from egregora_v3.core.types import Document
from egregora_v3.infra.schema import TABLE_NAME, UNIFIED_SCHEMA

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class DuckDBRepository:
    """Repository implementation using DuckDB and Ibis.

    Manages the single 'documents' table.
    """

    def __init__(self, backend: BaseBackend, table_name: str = TABLE_NAME):
        self.backend = backend
        self.table_name = table_name
        self._ensure_table()

    def _ensure_table(self):
        """Ensure the documents table exists."""
        if self.table_name not in self.backend.list_tables():
            self.backend.create_table(self.table_name, schema=UNIFIED_SCHEMA)
            logger.info(f"Created table '{self.table_name}' with Unified Schema.")

    @property
    def table(self):
        return self.backend.table(self.table_name)

    def save(self, doc: Any) -> None:
        """Upsert a document.

        If a document with the same ID exists, it is replaced.
        """
        # Auto-convert legacy documents
        if not isinstance(doc, Document):
            if hasattr(doc, "document_id") and hasattr(doc, "type"):
                doc = Document.from_legacy(doc)
            else:
                raise TypeError(f"Expected V3 Document or legacy Document, got {type(doc)}")

        row = self._document_to_row(doc)

        # DuckDB generic upsert is tricky with Ibis.
        # Strategy: Delete then Insert (within transaction if possible, or naive)
        # Or use generic SQL "INSERT OR REPLACE" if DuckDB supports it via Ibis raw SQL.
        # Ibis doesn't strictly support upsert across all backends.
        # For DuckDB, we can use "INSERT OR REPLACE INTO table ...".

        # Naive approach for now: Check existence, delete if exists, insert.
        # Note: This is not atomic without transaction management.

        # Check if ID exists
        t = self.table
        exists = t.filter(t.id == doc.id).count().execute() > 0

        if exists:
            # Delete logic requires raw SQL or a specific Ibis method if available.
            # Ibis generally discourages mutation.
            # For DuckDB backend, we might have to use raw SQL for deletion/upsert.
            self._execute_raw_sql(f"DELETE FROM {self.table_name} WHERE id = ?", params=[doc.id])

        # Insert
        self.backend.insert(self.table_name, [row])

    def get(self, doc_id: str) -> Document | None:
        """Retrieve a document by ID."""
        t = self.table
        result = t.filter(t.id == doc_id).execute()
        if result.empty:
            return None

        row = result.iloc[0].to_dict()
        return self._row_to_document(row)

    def list_collection(self, collection_name: str) -> Iterator[Document]:
        """List all documents in a collection."""
        t = self.table
        # Return iterator to avoid loading all into memory at once if large?
        # For now, simplistic execution.
        rows = t.filter(t.collection == collection_name).execute().to_dict('records')
        for row in rows:
            yield self._row_to_document(row)

    def get_high_water_mark(self, collection_name: str) -> datetime | None:
        """Get the max 'updated' timestamp for a collection."""
        t = self.table
        result = t.filter(t.collection == collection_name).aggregate(max_updated=t.updated.max()).execute()
        val = result.iloc[0]['max_updated']
        return val if pd_not_nat(val) else None

    def _document_to_row(self, doc: Document) -> dict[str, Any]:
        """Convert Document object to database row dict."""
        return {
            "id": doc.id,
            "collection": doc.collection,
            "doc_type": doc.doc_type.value if hasattr(doc.doc_type, "value") else str(doc.doc_type),
            "title": doc.title,
            "content": doc.content,
            "updated": doc.updated,
            "published": doc.published,
            "summary": doc.summary,

            # JSON serialization
            "authors": json.dumps([a.model_dump() for a in doc.authors]),
            "links": json.dumps([l.model_dump() for l in doc.links]),
            "tags": json.dumps([c.model_dump() for c in doc.categories]), # Mapping 'categories' to 'tags' column
            "extensions": json.dumps(doc.extensions),
            "internal_metadata": json.dumps(doc.internal_metadata),

            "parent_id": doc.parent_id,
            "embedding": doc.embedding,
            "searchable": doc.searchable
        }

    def _row_to_document(self, row: dict[str, Any]) -> Document:
        """Convert database row dict to Document object."""

        def _safe_load_json(val: Any, default: Any) -> Any:
            if val is None:
                return default
            if isinstance(val, (dict, list)):
                return val
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return default
            return default

        # Deserialize JSON
        authors = _safe_load_json(row["authors"], [])
        links = _safe_load_json(row["links"], [])
        tags = _safe_load_json(row["tags"], []) # Map back to categories
        extensions = _safe_load_json(row["extensions"], {})
        internal_metadata = _safe_load_json(row["internal_metadata"], {})

        # doc_type conversion
        from egregora_v3.core.types import DocumentType, DocumentStatus, Document

        return Document(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            updated=row["updated"],
            published=row["published"],
            summary=row["summary"],

            doc_type=DocumentType(row["doc_type"]),
            collection=row["collection"],

            authors=authors,
            links=links,
            categories=tags,
            extensions=extensions,
            internal_metadata=internal_metadata,

            parent_id=row["parent_id"],
            embedding=row["embedding"],
            searchable=row["searchable"]
        )

    def _execute_raw_sql(self, sql: str, params: list[Any] = None):
        """Helper to execute raw SQL on the underlying backend."""
        # This is backend-specific. Assuming DuckDB backend via Ibis.
        if hasattr(self.backend, "con"):
            self.backend.con.execute(sql, params or [])
        elif hasattr(self.backend, "raw_sql"):
            # Ibis 9+ might expose raw_sql differently
            self.backend.raw_sql(sql)
        else:
            raise NotImplementedError("Backend does not support raw SQL execution needed for deletes.")

def pd_not_nat(val):
    """Check if pandas value is not NaT (Not a Time)."""
    import pandas as pd
    return val is not None and not pd.isna(val)
