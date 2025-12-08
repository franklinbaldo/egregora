from __future__ import annotations

import json
from pathlib import Path

import duckdb

from egregora_v3.core.ports import DocumentRepository
from egregora_v3.core.types import Document, DocumentType, Entry


class DuckDBDocumentRepository(DocumentRepository):
    """DuckDB-backed repository for Documents and Entries.

    Uses a single DuckDB connection (file or in-memory).
    Stores data in two tables: 'documents' and 'entries'.
    Serialized complex fields (links, authors) as JSON.
    """

    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self.con = duckdb.connect(str(db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize tables if they don't exist."""
        # Entries Table
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                updated TIMESTAMP,
                published TIMESTAMP,
                content TEXT,
                summary TEXT,
                links JSON,
                authors JSON,
                categories JSON,
                extensions JSON,
                internal_metadata JSON,
                in_reply_to JSON,
                source_json JSON,
                raw_json JSON  -- Full dump for reconstruction
            )
        """)

        # Documents Table (Extends Entry)
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id VARCHAR PRIMARY KEY,
                title VARCHAR,
                updated TIMESTAMP,
                published TIMESTAMP,
                content TEXT,
                summary TEXT,
                links JSON,
                authors JSON,
                categories JSON,
                extensions JSON,
                internal_metadata JSON,
                in_reply_to JSON,
                doc_type VARCHAR,
                status VARCHAR,
                searchable BOOLEAN,
                raw_json JSON
            )
        """)

    def save(self, doc: Document) -> Document:
        """Save a Document."""
        raw_json = doc.model_dump_json()
        data = doc.model_dump()

        self.con.execute(
            """
            INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.id,
                doc.title,
                doc.updated,
                doc.published,
                doc.content,
                doc.summary,
                json.dumps(data.get("links")),
                json.dumps(data.get("authors")),
                json.dumps(data.get("categories")),
                json.dumps(data.get("extensions")),
                json.dumps(data.get("internal_metadata")),
                json.dumps(data.get("in_reply_to")) if doc.in_reply_to else None,
                doc.doc_type.value,
                doc.status.value,
                doc.searchable,
                raw_json,
            ),
        )
        return doc

    def get(self, doc_id: str) -> Document | None:
        """Get a Document by ID."""
        row = self.con.execute("SELECT raw_json FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not row:
            return None
        return Document.model_validate_json(row[0])

    def list(self, *, doc_type: DocumentType | None = None) -> list[Document]:
        """List documents, optionally filtering by type."""
        if doc_type:
            rows = self.con.execute(
                "SELECT raw_json FROM documents WHERE doc_type = ?", (doc_type.value,)
            ).fetchall()
        else:
            rows = self.con.execute("SELECT raw_json FROM documents").fetchall()

        return [Document.model_validate_json(r[0]) for r in rows]

    def exists(self, doc_id: str) -> bool:
        """Check if a document exists."""
        count = self.con.execute("SELECT COUNT(*) FROM documents WHERE id = ?", (doc_id,)).fetchone()[0]
        return count > 0

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        self.con.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def save_entry(self, entry: Entry) -> None:
        """Save an Entry."""
        raw_json = entry.model_dump_json()
        data = entry.model_dump()

        self.con.execute(
            """
            INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.title,
                entry.updated,
                entry.published,
                entry.content,
                entry.summary,
                json.dumps(data.get("links")),
                json.dumps(data.get("authors")),
                json.dumps(data.get("categories")),
                json.dumps(data.get("extensions")),
                json.dumps(data.get("internal_metadata")),
                json.dumps(data.get("in_reply_to")) if entry.in_reply_to else None,
                json.dumps(data.get("source")),
                raw_json,
            ),
        )

    def get_entry(self, entry_id: str) -> Entry | None:
        """Get an Entry by ID."""
        row = self.con.execute("SELECT raw_json FROM entries WHERE id = ?", (entry_id,)).fetchone()
        if not row:
            return None
        return Entry.model_validate_json(row[0])

    def get_entries_by_source(self, source_id: str) -> list[Entry]:
        """Get entries by source ID (not fully implemented in schema yet, fallback to all or scan).

        Note: The current schema doesn't strictly index 'source_id' at top level, it's in source_json.
        For V3 MVP, we might implement this via JSON extraction or just return empty if not needed immediately.
        Let's implement a JSON extraction query.
        """
        # DuckDB JSON extraction: source_json->>'id'
        rows = self.con.execute(
            "SELECT raw_json FROM entries WHERE json_extract_string(source_json, '$.id') = ?", (source_id,)
        ).fetchall()
        return [Entry.model_validate_json(r[0]) for r in rows]
