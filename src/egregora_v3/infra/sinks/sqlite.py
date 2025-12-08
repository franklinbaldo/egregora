"""SQLite Output Sink for exporting feeds to SQLite database."""

import json
import sqlite3
from pathlib import Path

from egregora_v3.core.types import Document, DocumentStatus, Feed


class SQLiteOutputSink:
    """Exports a Feed to a SQLite database.

    Creates a 'documents' table with all document fields.
    Only exports documents with status=PUBLISHED.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the SQLite output sink.

        Args:
            db_path: Path where the SQLite database will be created

        """
        self.db_path = Path(db_path)

    def publish(self, feed: Feed) -> None:
        """Publish the feed to a SQLite database.

        Args:
            feed: The Feed to publish

        Only publishes documents with status=PUBLISHED.
        Creates parent directories if they don't exist.
        Overwrites existing database.

        """
        # Create parent directories if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing database to start fresh
        if self.db_path.exists():
            self.db_path.unlink()

        # Create database and table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create documents table
        cursor.execute("""
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                doc_type TEXT NOT NULL,
                status TEXT NOT NULL,
                published TEXT,
                updated TEXT NOT NULL,
                authors TEXT,
                categories TEXT,
                links TEXT
            )
        """)

        # Filter published documents
        published_docs = [
            entry
            for entry in feed.entries
            if isinstance(entry, Document) and entry.status == DocumentStatus.PUBLISHED
        ]

        # Insert documents
        for doc in published_docs:
            self._insert_document(cursor, doc)

        conn.commit()
        conn.close()

    def _insert_document(self, cursor: sqlite3.Cursor, doc: Document) -> None:
        """Insert a single document into the database.

        Args:
            cursor: SQLite cursor
            doc: Document to insert

        """
        # Serialize lists to JSON
        authors_json = json.dumps([author.model_dump() for author in doc.authors]) if doc.authors else None
        categories_json = json.dumps([cat.model_dump() for cat in doc.categories]) if doc.categories else None
        links_json = json.dumps([link.model_dump() for link in doc.links]) if doc.links else None

        # Format timestamps as ISO 8601
        published_str = doc.published.isoformat() if doc.published else None
        updated_str = doc.updated.isoformat()

        cursor.execute(
            """
            INSERT INTO documents (
                id, title, content, summary, doc_type, status,
                published, updated, authors, categories, links
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.id,
                doc.title,
                doc.content,
                doc.summary,
                doc.doc_type.value,
                doc.status.value,
                published_str,
                updated_str,
                authors_json,
                categories_json,
                links_json,
            ),
        )
