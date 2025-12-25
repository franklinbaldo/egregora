import builtins
import contextlib
from datetime import datetime

import ibis
from ibis.expr.types import Table

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType, Entry

_DOCUMENT_TYPE_VALUES = {item.value for item in DocumentType}


class DuckDBDocumentRepository(DocumentRepository):
    """DuckDB-backed document storage."""

    def __init__(self, conn: ibis.BaseBackend) -> None:
        self.conn = conn
        self.table_name = "documents"

    def initialize(self) -> None:
        """Creates the table with a primary key if it doesn't exist."""
        if self.table_name not in self.conn.list_tables():
            # Enforce the creation of a PRIMARY KEY for reliable upserts.
            # This follows the "One good path" heuristic, avoiding complex fallbacks.
            self.conn.con.execute(f"""
                CREATE TABLE {self.table_name} (
                    id VARCHAR PRIMARY KEY,
                    doc_type VARCHAR,
                    json_data JSON,
                    updated TIMESTAMP
                )
            """)

    def _get_table(self) -> Table:
        return self.conn.table(self.table_name)

    def save(self, doc: Document) -> Document:
        """Saves a document to the repository."""
        self._upsert_record(doc.id, doc.doc_type.value, doc.model_dump_json(), doc.updated)
        return doc

    def _upsert_record(self, record_id: str, doc_type: str, json_data: str, updated: datetime) -> None:
        """
        Helper to upsert a record using a reliable INSERT OR REPLACE.
        This assumes the table has a PRIMARY KEY, enforced by `initialize`.
        """
        query = f"""
            INSERT OR REPLACE INTO {self.table_name} (id, doc_type, json_data, updated)
            VALUES (?, ?, ?, ?)
        """
        self.conn.con.execute(query, [record_id, doc_type, json_data, updated])

    def _hydrate_object(self, json_val: str | dict, doc_type_val: str) -> Entry:
        """Centralized helper to deserialize JSON into Entry or Document."""
        is_document = doc_type_val in _DOCUMENT_TYPE_VALUES

        model_class = Document if is_document else Entry
        validator = model_class.model_validate if isinstance(json_val, dict) else model_class.model_validate_json
        return validator(json_val)

    def get(self, doc_id: str) -> Document | None:
        """Retrieves a document by ID."""
        t = self._get_table()
        # Push all filtering into the query for declarative style.
        query = t.filter(t.id == doc_id).filter(t.doc_type != "_ENTRY_").select("doc_type", "json_data")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        # We know it's a Document because of the filter, so the cast is safe.
        return self._hydrate_object(row["json_data"], row["doc_type"])

    def list(
        self,
        *,
        doc_type: DocumentType | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[Document]:
        """Lists documents, optionally filtered by type, with sorting and limiting."""
        t = self._get_table()
        # Always exclude raw entries.
        query = t.filter(t.doc_type != "_ENTRY_")
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)

        # Add sorting and limiting to the query
        if order_by:
            # Default to descending order for fields like 'updated'
            query = query.order_by(ibis.desc(order_by))

        if limit:
            query = query.limit(limit)

        result = query.select("doc_type", "json_data").execute()

        # We know these are Documents, so the list comprehension cast is safe.
        return [self._hydrate_object(row["json_data"], row["doc_type"]) for _, row in result.iterrows()]

    def delete(self, doc_id: str) -> None:
        """Deletes a document by ID using a direct, parameterized query."""
        query = f"DELETE FROM {self.table_name} WHERE id = ?"
        self.conn.con.execute(query, [doc_id])

    def exists(self, doc_id: str) -> bool:
        """Checks if a document exists."""
        t = self._get_table()
        count = t.filter(t.id == doc_id).count().execute()
        return count > 0

    def count(self, *, doc_type: DocumentType | None = None) -> int:
        """Counts documents, optionally filtered by type."""
        t = self._get_table()
        # Always exclude raw entries.
        query = t.filter(t.doc_type != "_ENTRY_")
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)

        return query.count().execute()

    # Entry methods

    def save_entry(self, entry: Entry) -> None:
        """
        Saves an Entry to the repository using polymorphism.
        Relies on the `doc_type` attribute of the entry to determine its type,
        avoiding imperative `isinstance` checks.
        """
        doc_type_val = getattr(entry, "doc_type", "_ENTRY_")
        if isinstance(doc_type_val, DocumentType):
            doc_type_val = doc_type_val.value

        json_data = entry.model_dump_json()
        self._upsert_record(entry.id, doc_type_val, json_data, entry.updated)

    def get_entry(self, entry_id: str) -> Entry | None:
        """Retrieves an Entry (or Document) by ID."""
        t = self._get_table()
        query = t.filter(t.id == entry_id).select("json_data", "doc_type")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        return self._hydrate_object(row["json_data"], row["doc_type"])

    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]:
        """Lists entries by source ID using raw SQL for reliable JSON extraction."""
        if not hasattr(self.conn, "con"):
            # This method relies on raw SQL for DuckDB's JSON support, which is more reliable than the Ibis API
            # for this purpose. If we don't have a raw connection, we can't proceed.
            return []

        sql = f"SELECT json_data, doc_type FROM {self.table_name} WHERE json_extract_string(json_data, '$.source.id') = ?"
        result = self.conn.con.execute(sql, [source_id]).fetch_df()

        return [self._hydrate_object(row["json_data"], row["doc_type"]) for _, row in result.iterrows()]
