"""CSV Output Sink for exporting feeds to CSV files."""

import csv
import json
from pathlib import Path

from egregora_v3.core.types import Document, DocumentStatus, Feed


class CSVOutputSink:
    """Exports a Feed to a CSV file.

    Creates one CSV file with all published documents.
    Each row represents a document with all fields.
    """

    def __init__(self, csv_path: Path) -> None:
        """Initialize the CSV output sink.

        Args:
            csv_path: Path where the CSV file will be created

        """
        self.csv_path = Path(csv_path)

    def publish(self, feed: Feed) -> None:
        """Publish the feed to a CSV file.

        Args:
            feed: The Feed to publish

        Only publishes documents with status=PUBLISHED.
        Creates parent directories if they don't exist.
        Overwrites existing file.

        """
        # Create parent directories if needed
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Filter published documents
        published_docs = [
            entry
            for entry in feed.entries
            if isinstance(entry, Document) and entry.status == DocumentStatus.PUBLISHED
        ]

        # Define CSV fieldnames
        fieldnames = [
            "id",
            "title",
            "content",
            "summary",
            "doc_type",
            "status",
            "published",
            "updated",
            "authors",
            "categories",
            "links",
        ]

        # Write CSV file
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for doc in published_docs:
                writer.writerow(self._document_to_row(doc))

    def _document_to_row(self, doc: Document) -> dict:
        """Convert a document to a CSV row dictionary.

        Args:
            doc: Document to convert

        Returns:
            Dictionary mapping fieldnames to values

        """
        # Serialize lists to JSON
        authors_json = (
            json.dumps([author.model_dump() for author in doc.authors])
            if doc.authors
            else ""
        )
        categories_json = (
            json.dumps([cat.model_dump() for cat in doc.categories])
            if doc.categories
            else ""
        )
        links_json = (
            json.dumps([link.model_dump() for link in doc.links])
            if doc.links
            else ""
        )

        # Format timestamps as ISO 8601
        published_str = doc.published.isoformat() if doc.published else ""
        updated_str = doc.updated.isoformat()

        return {
            "id": doc.id,
            "title": doc.title,
            "content": doc.content or "",
            "summary": doc.summary or "",
            "doc_type": doc.doc_type.value,
            "status": doc.status.value,
            "published": published_str,
            "updated": updated_str,
            "authors": authors_json,
            "categories": categories_json,
            "links": links_json,
        }
