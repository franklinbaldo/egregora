import builtins
import contextlib
from datetime import datetime

import ibis
from ibis.expr.types import Table

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType, Entry


class DuckDBDocumentRepository(DocumentRepository):
    """DuckDB-backed document storage."""

    def __init__(self, conn: ibis.BaseBackend) -> None:
        self.conn = conn
        self.table_name = "documents"

    def initialize(self) -> None:
        """Creates the table if it doesn't exist."""
        # Check if table exists
        if self.table_name not in self.conn.list_tables():
            # Define schema based on Document fields
            # We store the full Document as a JSON blob plus some extracted columns for querying
            # Note: For DuckDB to support INSERT OR REPLACE (upsert), we need a primary key.
            # Ibis 9.0 create_table doesn't easily expose PK creation via schema object directly in a backend-agnostic way often,
            # but for DuckDB we can execute raw SQL to create table with PK.

            if hasattr(self.conn, "con"):
                # Use raw SQL to create table with PRIMARY KEY
                self.conn.con.execute(f"""
                    CREATE TABLE {self.table_name} (
                        id VARCHAR PRIMARY KEY,
                        doc_type VARCHAR,
                        json_data JSON,
                        updated TIMESTAMP
                    )
                """)
            else:
                # Fallback to Ibis create_table (might lack PK constraint)
                schema = ibis.schema(
                    {
                        "id": "string",
                        "doc_type": "string",
                        "json_data": "json",
                        "updated": "timestamp",
                    }
                )
                self.conn.create_table(self.table_name, schema=schema)
                # If we couldn't create PK, upsert might fail. We handle this in save.

    def _get_table(self) -> Table:
        return self.conn.table(self.table_name)

    def save(self, doc: Document) -> Document:
        """Saves a document to the repository."""
        self._upsert_record(doc.id, doc.doc_type.value, doc.model_dump_json(), doc.updated)
        return doc

    def _upsert_record(self, record_id: str, doc_type: str, json_data: str, updated: datetime) -> None:
        """Helper to upsert a record with handling for PK constraints."""
        if hasattr(self.conn, "con"):
            # Use parameterized INSERT OR REPLACE (upsert)
            try:
                query = f"""
                    INSERT OR REPLACE INTO {self.table_name} (id, doc_type, json_data, updated)
                    VALUES (?, ?, ?, ?)
                """
                self.conn.con.execute(query, [record_id, doc_type, json_data, updated])
            except Exception as e:
                # If "ON CONFLICT is a no-op" error occurs, it means no PK.
                # Fallback to delete + insert pattern manually.
                if "ON CONFLICT is a no-op" in str(e):
                    self._manual_upsert_record(record_id, doc_type, json_data, updated)
                else:
                    raise
        else:
            self._manual_upsert_record(record_id, doc_type, json_data, updated)

    def _manual_upsert(self, doc: Document, json_data: str) -> None:
        """Deprecated: Use _manual_upsert_record instead."""
        self._manual_upsert_record(doc.id, doc.doc_type.value, json_data, doc.updated)

    def _manual_upsert_record(self, record_id: str, doc_type: str, json_data: str, updated: datetime) -> None:
        """Manual delete + insert for backends/tables without PK constraint."""
        # Safe delete first
        with contextlib.suppress(Exception):
            self.delete(record_id)

        # Insert via Ibis
        data = {
            "id": record_id,
            "doc_type": doc_type,
            "json_data": json_data,
            "updated": updated,
        }
        self.conn.insert(self.table_name, [data])

    def get(self, doc_id: str) -> Document | None:
        """Retrieves a document by ID."""
        # This explicitly expects a Document (subset of Entry with specific fields/type)
        t = self._get_table()
        query = t.filter(t.id == doc_id).select("doc_type", "json_data")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        # Verify it is a Document (has valid doc_type from DocumentType enum)
        # However, historically get() just inflated whatever into Document.
        # Now we have hybrid table.
        # If doc_type is "_ENTRY_", Document.model_validate might fail if it misses required fields
        # or it might succeed but effectively be wrong type.
        # Strict typing: if we called get() we expect Document.
        # If we find an Entry, we might return None or raise error?
        # Or try to parse.

        json_val = row["json_data"]

        # If it's a raw entry, we can't really return it as a Document easily unless we cast it.
        # But get() signature is Document | None.
        # If type is _ENTRY_, it's NOT a Document.
        if row["doc_type"] == "_ENTRY_":
            return None

        if isinstance(json_val, dict):
            return Document.model_validate(json_val)

        return Document.model_validate_json(json_val)

    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]:
        """Lists documents, optionally filtered by type."""
        t = self._get_table()
        query = t
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)
        else:
            # Exclude raw entries if listing "Documents"
            query = query.filter(query.doc_type != "_ENTRY_")

        # Select JSON data
        result = query.select("json_data").execute()

        docs = []
        for json_val in result["json_data"]:
            if isinstance(json_val, dict):
                docs.append(Document.model_validate(json_val))
            else:
                docs.append(Document.model_validate_json(json_val))

        return docs

    def delete(self, doc_id: str) -> None:
        """Deletes a document by ID."""
        # Use parameterized query if possible via underlying connection
        if hasattr(self.conn, "con"):
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            self.conn.con.execute(query, [doc_id])
        else:
            # Fallback to Ibis delete if available, otherwise raise error
            # Refusing to use unsafe raw SQL interpolation.
            try:
                t = self._get_table()
                # Ibis does not have a standard 'delete' method exposed on Table/Expression in all versions/backends
                # But some backends might support it via extension or future versions.
                # If this fails, we must error out rather than be unsafe.
                t.filter(t.id == doc_id).delete()
            except Exception as err:
                msg = "Backend does not support a safe delete operation via Ibis or parameterized SQL."
                raise NotImplementedError(msg) from err

    def exists(self, doc_id: str) -> bool:
        """Checks if a document exists."""
        t = self._get_table()
        count = t.filter(t.id == doc_id).count().execute()
        return count > 0

    # Entry methods

    def save_entry(self, entry: Entry) -> None:
        """Saves an Entry to the repository."""
        if isinstance(entry, Document):
            self.save(entry)
            return

        json_data = entry.model_dump_json()
        doc_type_val = "_ENTRY_"

        # Reuse helper for consistency
        self._upsert_record(entry.id, doc_type_val, json_data, entry.updated)

    def get_entry(self, entry_id: str) -> Entry | None:
        """Retrieves an Entry (or Document) by ID."""
        t = self._get_table()
        query = t.filter(t.id == entry_id).select("json_data", "doc_type")
        result = query.execute()

        if result.empty:
            return None

        row = result.iloc[0]
        json_val = row["json_data"]
        doc_type_val = row["doc_type"]

        # Check if it's a Document (has a valid DocumentType)
        is_document = any(doc_type_val == item.value for item in DocumentType)

        if is_document:
            if isinstance(json_val, dict):
                return Document.model_validate(json_val)
            return Document.model_validate_json(json_val)

        # Otherwise treat as raw Entry
        if isinstance(json_val, dict):
            return Entry.model_validate(json_val)
        return Entry.model_validate_json(json_val)

    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]:
        """Lists entries by source ID."""
        # Use DuckDB raw SQL directly for JSON extraction to avoid Ibis type mismatch issues
        if hasattr(self.conn, "con"):
            # DuckDB raw SQL for JSON extraction
            sql = f"SELECT json_data, doc_type FROM {self.table_name} WHERE json_extract_string(json_data, '$.source.id') = ?"
            result = self.conn.con.execute(sql, [source_id]).fetch_df()
        else:
            # Fallback: try Ibis JSON access for other backends
            t = self._get_table()
            try:
                query = t.filter(t.json_data["source"]["id"] == source_id)
                result = query.select("json_data", "doc_type").execute()
            except (AttributeError, NotImplementedError, TypeError, KeyError):
                # If we can't filter, return empty (or could fetch all and filter in python, but that's slow)
                return []

        entries = []
        for _, row in result.iterrows():
            json_val = row["json_data"]
            doc_type_val = row["doc_type"]

            is_document = any(doc_type_val == item.value for item in DocumentType)

            if is_document:
                if isinstance(json_val, dict):
                    entries.append(Document.model_validate(json_val))
                else:
                    entries.append(Document.model_validate_json(json_val))
            elif isinstance(json_val, dict):
                entries.append(Entry.model_validate(json_val))
            else:
                entries.append(Entry.model_validate_json(json_val))

        return entries
