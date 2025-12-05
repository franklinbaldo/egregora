import builtins

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
        json_data = doc.model_dump_json()

        if hasattr(self.conn, "con"):
            # Use parameterized INSERT OR REPLACE (upsert)
            try:
                query = f"""
                    INSERT OR REPLACE INTO {self.table_name} (id, doc_type, json_data, updated)
                    VALUES (?, ?, ?, ?)
                """
                self.conn.con.execute(query, [doc.id, doc.doc_type.value, json_data, doc.updated])
            except Exception as e:
                # If "ON CONFLICT is a no-op" error occurs, it means no PK.
                # Fallback to delete + insert pattern manually.
                if "ON CONFLICT is a no-op" in str(e):
                    self._manual_upsert(doc, json_data)
                else:
                    raise
        else:
            self._manual_upsert(doc, json_data)

        return doc

    def _manual_upsert(self, doc: Document, json_data: str) -> None:
        """Manual delete + insert for backends/tables without PK constraint."""
        # Safe delete first
        self.delete(doc.id)

        # Insert via Ibis
        data = {
            "id": doc.id,
            "doc_type": doc.doc_type.value,
            "json_data": json_data,
            "updated": doc.updated,
        }
        self.conn.insert(self.table_name, [data])

    def get(self, doc_id: str) -> Document | None:
        """Retrieves a document by ID."""
        t = self._get_table()
        query = t.filter(t.id == doc_id).select("json_data")
        result = query.execute()

        if result.empty:
            return None

        json_val = result.iloc[0]["json_data"]
        # Ibis DuckDB backend returns Python dict/list for JSON columns
        if isinstance(json_val, dict):
            return Document.model_validate(json_val)

        return Document.model_validate_json(json_val)

    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]:
        """Lists documents, optionally filtered by type."""
        t = self._get_table()
        query = t
        if doc_type:
            query = query.filter(query.doc_type == doc_type.value)

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

    # Entry methods (stubbed for now or can reuse same table with different type/logic if we want single table)

    def save_entry(self, entry: Entry) -> None:
        # TODO: Implement Entry persistence
        pass

    def get_entry(self, entry_id: str) -> Entry | None:
        # TODO: Implement Entry retrieval
        return None

    def get_entries_by_source(self, source_id: str) -> builtins.list[Entry]:
        # TODO: Implement Entry listing by source
        return []
