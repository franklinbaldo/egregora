"""SQLite Output Sink for exporting feeds to SQLite database."""

import json
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Any

from egregora_v3.core.types import Document, Feed


TABLE_SCHEMA = OrderedDict([
    ("id", "TEXT PRIMARY KEY"),
    ("title", "TEXT NOT NULL"),
    ("content", "TEXT"),
    ("summary", "TEXT"),
    ("doc_type", "TEXT NOT NULL"),
    ("status", "TEXT NOT NULL"),
    ("published", "TEXT"),
    ("updated", "TEXT NOT NULL"),
    ("authors", "TEXT"),
    ("categories", "TEXT"),
    ("links", "TEXT"),
])


def _document_to_record(doc: Document) -> dict[str, Any]:
    """Serialize a Document to a dictionary for database insertion."""
    return {
        "id": doc.id,
        "title": doc.title,
        "content": doc.content,
        "summary": doc.summary,
        "doc_type": doc.doc_type.value,
        "status": doc.status.value,
        "published": doc.published.isoformat() if doc.published else None,
        "updated": doc.updated.isoformat(),
        "authors": json.dumps([author.model_dump() for author in doc.authors]) if doc.authors else None,
        "categories": json.dumps([cat.model_dump() for cat in doc.categories]) if doc.categories else None,
        "links": json.dumps([link.model_dump() for link in doc.links]) if doc.links else None,
    }


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
        columns = ", ".join(TABLE_SCHEMA.keys())
        placeholders = ", ".join("?" for _ in TABLE_SCHEMA)
        self._insert_statement = f"INSERT INTO documents ({columns}) VALUES ({placeholders})"

    def publish(self, feed: Feed) -> None:
        """Publish the feed to a SQLite database.

        Args:
            feed: The Feed to publish

        Only publishes documents with status=PUBLISHED.
        Creates parent directories if they don't exist.
        Overwrites existing database.

        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self._create_table(cursor)

        for doc in feed.get_published_documents():
            record = _document_to_record(doc)
            self._insert_record(cursor, record)

        conn.commit()
        conn.close()

    def _create_table(self, cursor: sqlite3.Cursor) -> None:
        """Create the documents table from TABLE_SCHEMA."""
        columns = ", ".join(f"{name} {dtype}" for name, dtype in TABLE_SCHEMA.items())
        cursor.execute(f"CREATE TABLE documents ({columns})")

    def _insert_record(self, cursor: sqlite3.Cursor, record: dict[str, Any]) -> None:
        """Insert a single document record into the database."""
        values = tuple(record[key] for key in TABLE_SCHEMA)
        cursor.execute(self._insert_statement, values)
