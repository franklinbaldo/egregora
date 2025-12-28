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
        if not hasattr(conn, "con"):
            msg = "DuckDBDocumentRepository requires a raw DuckDB connection via the '.con' attribute."
            raise ValueError(msg)
        self.conn = conn
        self.table_name = "documents"

    def initialize(self) -> None:
        """Creates the 'documents' table with a primary key if it doesn't exist."""
        self.conn.con.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id VARCHAR PRIMARY KEY,
                doc_type VARCHAR,
                json_data JSON,
                updated TIMESTAMP
            )
        """)

    def _get_table(self) -> Table:
        return self.conn.table(self.table_name)

    def save(self, entry: Entry) -> Entry:
        """Saves an Entry or Document to the repository."""
        if isinstance(entry, Document):
            doc_type_val = entry.doc_type.value
        else:
            doc_type_val = "_ENTRY_"

        json_data = entry.model_dump_json()
        self._upsert_record(entry.id, doc_type_val, json_data, entry.updated)
        return entry

    def _upsert_record(self, record_id: str, doc_type: str, json_data: str, updated: datetime) -> None:
        """Helper to perform a raw SQL upsert (INSERT OR REPLACE)."""
        query = f"""
            INSERT OR REPLACE INTO {self.table_name} (id, doc_type, json_data, updated)
            VALUES (?, ?, ?, ?)
        """
        self.conn.con.execute(query, [record_id, doc_type, json_data, updated])

    def _hydrate_entry(self, json_val: str | dict, doc_type_val: str) -> Entry:
        """Deserialize JSON into an Entry or Document, depending on its type."""
        is_document = doc_type_val in _DOCUMENT_TYPE_VALUES
        model_class = Document if is_document else Entry
        validator = (
            model_class.model_validate
            if isinstance(json_val, dict)
            else model_class.model_validate_json
        )
        return validator(json_val)

    def _hydrate_document(self, json_val: str | dict) -> Document:
        """Deserialize JSON into a Document."""
        # This helper assumes the caller has already confirmed the object is a Document.
        validator = (
            Document.model_validate
            if isinstance(json_val, dict)
            else Document.model_validate_json
        )
        return validator(json_val)

    def get(self, doc_id: str) -> Document | None:
        """Retrieves a document by ID."""
        t = self._get_table()
        query = t.filter(t.id == doc_id).select("doc_type", "json_data")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        doc_type_val = row["doc_type"]

        # get() specifically retrieves Documents, not raw Entries.
        if doc_type_val == "_ENTRY_":
            return None

        # We know it's a Document, so the cast is safe.
        return self._hydrate_document(row["json_data"])

    def list(
        self,
        *,
        doc_type: DocumentType | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> list[Document]:
        """Lists documents, optionally filtered, sorted, and limited."""
        t = self._get_table()
        query = t

        # Filtering
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)
        else:
            query = query.filter(query.doc_type != "_ENTRY_")

        # Sorting
        if order_by:
            order_desc = order_by.startswith("-")
            order_col = order_by.lstrip("-")

            if hasattr(query, order_col):
                col = getattr(query, order_col)
                query = query.order_by(ibis.desc(col) if order_desc else col)
            else:
                # Handle sorting by fields inside the JSON blob if necessary in the future
                # For now, we only support top-level columns like 'updated'.
                pass

        # Limiting
        if limit:
            query = query.limit(limit)

        result = query.select("doc_type", "json_data").execute()
        return [self._hydrate_document(row["json_data"]) for _, row in result.iterrows()]

    def delete(self, doc_id: str) -> None:
        """Deletes a document by ID using a parameterized query."""
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
        query = t
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)
        else:
            # Exclude raw entries if counting all "Documents"
            query = query.filter(query.doc_type != "_ENTRY_")

        return query.count().execute()

    # Entry methods

    def get_entry(self, entry_id: str) -> Entry | None:
        """Retrieves an Entry (or Document) by ID."""
        t = self._get_table()
        query = t.filter(t.id == entry_id).select("json_data", "doc_type")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        return self._hydrate_entry(row["json_data"], row["doc_type"])

    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]:
        """Lists entries by source ID using raw SQL for reliable JSON extraction."""
        if not hasattr(self.conn, "con"):
            # This method relies on raw SQL for DuckDB's JSON support, which is more reliable than the Ibis API
            # for this purpose. If we don't have a raw connection, we can't proceed.
            return []

        sql = f"SELECT json_data, doc_type FROM {self.table_name} WHERE json_extract_string(json_data, '$.source.id') = ?"
        result = self.conn.con.execute(sql, [source_id]).fetch_df()

        return [self._hydrate_entry(row["json_data"], row["doc_type"]) for _, row in result.iterrows()]
