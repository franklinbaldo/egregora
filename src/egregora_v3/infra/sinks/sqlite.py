"""SQLite Output Sink for exporting feeds to SQLite database."""

import json
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Any

from egregora.core.types import Document, Feed


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
    # `model_dump` with `mode='json'` serializes nested Pydantic models.
    # We then re-serialize the list fields into JSON strings for the DB.
    record = doc.model_dump(mode="json")
    for key in ["authors", "categories", "links"]:
        if key in record and record[key] is not None:
            record[key] = json.dumps(record[key])
    return record


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
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()

        # Declarative table creation from schema
        columns_def = ", ".join(f"{name} {dtype}" for name, dtype in TABLE_SCHEMA.items())
        create_table_sql = f"CREATE TABLE documents ({columns_def})"

        # Declarative insert statement from schema
        columns = ", ".join(TABLE_SCHEMA.keys())
        placeholders = ", ".join("?" for _ in TABLE_SCHEMA)
        insert_sql = f"INSERT INTO documents ({columns}) VALUES ({placeholders})"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)

            for doc in feed.get_published_documents():
                record = _document_to_record(doc)
                values = tuple(record.get(key) for key in TABLE_SCHEMA)
                cursor.execute(insert_sql, values)

            conn.commit()
