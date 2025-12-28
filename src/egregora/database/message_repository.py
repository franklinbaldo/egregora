"""Repository for querying the messages table."""

from __future__ import annotations

import mimetypes
import re
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from egregora.data_primitives.document import Document, DocumentType
from egregora.database.streaming import ensure_deterministic_order, stream_ibis
from egregora.orchestration.pipelines.modules.media import extract_urls, find_media_references
from egregora.utils.datetime_utils import ensure_datetime

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
    from ibis.expr.types import Table


_MARKDOWN_LINK_PATTERN = re.compile(r"(?:!\[|\[)[^\]]*\]\([^)]*?([^/)]+\.\w+)\)")
_UUID_PATTERN = re.compile(r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\.\w+)")

# Pattern to match simple media filenames with known extensions
_MEDIA_FILE_PATTERN = re.compile(
    r"\b([\w\-\.]+\.(?:jpg|jpeg|png|gif|webp|mp4|mov|3gp|avi|opus|ogg|mp3|m4a|aac|pdf|doc|docx))\b",
    re.IGNORECASE,
)


class MessageRepository:
    """Provides an interface for querying the messages table."""

    def __init__(self, db: DuckDBBackend) -> None:
        """Initializes the repository with a database connection.

        Args:
            db: An Ibis DuckDB backend connection.

        """
        self._db = db

    def get_url_enrichment_candidates(
        self, messages_table: Table, max_enrichments: int
    ) -> list[tuple[str, dict[str, Any]]]:
        """Extract unique URL candidates with metadata, up to max_enrichments."""
        if max_enrichments <= 0:
            return []

        url_metadata: dict[str, dict[str, Any]] = {}
        discovered_count = 0

        for batch in self._iter_table_batches(
            messages_table.select(
                "ts",
                "text",
                "event_id",
                "tenant_id",
                "source",
                "thread_id",
                "author_uuid",
                "created_at",
                "created_by_run",
            )
        ):
            for row in batch:
                if discovered_count >= max_enrichments:
                    break
                discovered_count = self._process_url_row(row, url_metadata, discovered_count, max_enrichments)

            if discovered_count >= max_enrichments:
                break

        sorted_items = sorted(
            url_metadata.items(),
            key=lambda item: (item[1]["ts"] is None, item[1]["ts"]),
        )
        return sorted_items[:max_enrichments]

    def _process_url_row(
        self,
        row: dict[str, Any],
        url_metadata: dict[str, dict[str, Any]],
        discovered_count: int,
        max_enrichments: int,
    ) -> int:
        """Process a single row for URL extraction."""
        message = row.get("text")
        if not message:
            return discovered_count
        urls = extract_urls(message)
        if not urls:
            return discovered_count

        timestamp = ensure_datetime(row.get("ts")) if row.get("ts") else None
        row_metadata = {
            "ts": timestamp,
            "event_id": self._uuid_to_str(row.get("event_id")),
            "tenant_id": row.get("tenant_id"),
            "source": row.get("source"),
            "thread_id": self._uuid_to_str(row.get("thread_id")),
            "author_uuid": self._uuid_to_str(row.get("author_uuid")),
            "created_at": row.get("created_at"),
            "created_by_run": self._uuid_to_str(row.get("created_by_run")),
        }

        for url in urls[:3]:
            existing = url_metadata.get(url)
            if existing is None:
                url_metadata[url] = row_metadata.copy()
                discovered_count += 1
                if discovered_count >= max_enrichments:
                    return discovered_count
            else:
                existing_ts = existing.get("ts")
                if timestamp is not None and (existing_ts is None or timestamp < existing_ts):
                    existing.update(row_metadata)
        return discovered_count

    def _iter_table_batches(self, table: Table, batch_size: int = 1000) -> Iterator[list[dict[str, Any]]]:
        """Stream table rows as batches of dictionaries without loading entire table into memory."""
        ordered_table = ensure_deterministic_order(table)
        yield from stream_ibis(ordered_table, self._db, batch_size=batch_size)

    def _uuid_to_str(self, value: Any) -> str | None:
        """Safely convert a UUID to a string, handling None."""
        if value is None:
            return None
        return str(value)

    def get_media_enrichment_candidates(
        self, messages_table: Table, media_mapping: dict, limit: int
    ) -> list[tuple[str, Any, dict[str, Any]]]:
        """Extract unique Media candidates with metadata."""
        if limit <= 0:
            return []

        unique_media: set[str] = set()
        metadata_lookup: dict[str, dict[str, Any]] = {}
        document_lookup: dict[str, Any] = {}

        for batch in self._iter_table_batches(
            messages_table.select(
                "ts",
                "text",
                "event_id",
                "tenant_id",
                "source",
                "thread_id",
                "author_uuid",
                "created_at",
                "created_by_run",
            )
        ):
            for row in batch:
                if len(unique_media) >= limit:
                    break

                message = row.get("text")
                if not message:
                    continue

                refs = self._find_media_references(message, row)
                if not refs:
                    continue

                timestamp = ensure_datetime(row.get("ts")) if row.get("ts") else None
                row_metadata = {
                    "ts": timestamp,
                    "event_id": self._uuid_to_str(row.get("event_id")),
                    "tenant_id": row.get("tenant_id"),
                    "source": row.get("source"),
                    "thread_id": self._uuid_to_str(row.get("thread_id")),
                    "author_uuid": self._uuid_to_str(row.get("author_uuid")),
                    "created_at": row.get("created_at"),
                    "created_by_run": self._uuid_to_str(row.get("created_by_run")),
                }

                for ref in set(refs):
                    if ref in unique_media:
                        existing = metadata_lookup.get(ref)
                        if existing:
                            existing_ts = existing.get("ts")
                            if existing_ts and timestamp and timestamp < existing_ts:
                                existing.update(row_metadata)
                        continue

                    unique_media.add(ref)
                    metadata_lookup[ref] = row_metadata.copy()

                    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, ref))
                    document_lookup[ref] = Document(
                        content=b"",
                        type=DocumentType.MEDIA,
                        id=doc_id,
                        metadata={
                            "filename": ref,
                            "original_filename": ref,
                            "media_type": mimetypes.guess_type(ref)[0] or "application/octet-stream",
                        },
                    )

            if len(unique_media) >= limit:
                break

        sorted_refs = sorted(
            unique_media, key=lambda r: (metadata_lookup[r]["ts"] is None, metadata_lookup[r]["ts"])
        )

        return [(ref, document_lookup[ref], metadata_lookup[ref]) for ref in sorted_refs[:limit]]

    def _find_media_references(self, message: str, row: dict[str, Any]) -> list[str]:
        """Find media references in a message."""
        refs = find_media_references(message)
        refs.extend(_MARKDOWN_LINK_PATTERN.findall(message))
        refs.extend(_MEDIA_FILE_PATTERN.findall(message))
        uuid_refs = _UUID_PATTERN.findall(message)
        refs.extend([u for u in uuid_refs if row.get("media_type")])
        return refs
