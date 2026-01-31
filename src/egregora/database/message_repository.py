"""Repository for querying the messages table."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import ibis
from ibis import udf

from egregora.data_primitives.datetime_utils import ensure_datetime
from egregora.data_primitives.document import Document, DocumentType
from egregora.database.streaming import ensure_deterministic_order, stream_ibis

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend
    from ibis.expr.types import Table


@udf.scalar.builtin
def regexp_extract_all(text: str, pattern: str, group: int = 0) -> list[str]:
    """Extract all matches of pattern from text."""


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

        # Regex to match URLs (equivalent to egregora.ops.media.URL_PATTERN)
        url_regex = r'https?://[^\s<>"{}|\\^`\[\]]+'

        # 1. Filter rows with text and extract URLs
        candidates = messages_table.filter(messages_table.text.notnull())
        candidates = candidates.mutate(urls=regexp_extract_all(candidates.text, url_regex))

        # 2. Unnest URLs to have one row per URL found
        candidates = candidates.select(
            url=candidates.urls.unnest(),
            ts=candidates.ts,
            event_id=candidates.event_id,
            tenant_id=candidates.tenant_id,
            source=candidates.source,
            thread_id=candidates.thread_id,
            author_uuid=candidates.author_uuid,
            created_at=candidates.created_at,
            created_by_run=candidates.created_by_run,
        )

        # 3. Filter existing enrichments (Anti Join)
        # We assume existing enrichments are in the same messages table with media_type='URL'
        # Note: This checks strictly against the DB. If there are pending enrichments not in DB,
        # they might be re-scheduled, but Enqueue logic also checks cache.
        try:
            existing_enrichments = messages_table.filter(messages_table.media_type == "URL").select(
                "media_url"
            )
            candidates = candidates.anti_join(
                existing_enrichments, candidates.url == existing_enrichments.media_url
            )
        except Exception:
            # Fallback if self-join fails or table structure is unexpected
            logger.exception("Failed to filter existing URL enrichments")

        # 4. Deduplicate: Keep the earliest occurrence of each URL
        # We group by URL and use a window function to rank occurrences by timestamp
        w = ibis.window(group_by="url", order_by="ts")
        candidates = candidates.mutate(rank=ibis.row_number().over(w))
        candidates = candidates.filter(candidates.rank == 0)

        # 5. Limit and sort
        # We order by URL as secondary key to ensure deterministic order for messages with same timestamp
        candidates = candidates.order_by(["ts", "url"]).limit(max_enrichments)

        # 6. Execute
        try:
            results = candidates.execute()
        except Exception:
            # Fallback to empty if query fails
            return []

        # 7. Format output
        output_items = []
        for row in results.to_dict("records"):
            url = row["url"]
            metadata = {
                "ts": ensure_datetime(row["ts"]) if row["ts"] else None,
                "event_id": self._uuid_to_str(row["event_id"]),
                "tenant_id": row["tenant_id"],
                "source": row["source"],
                "thread_id": self._uuid_to_str(row["thread_id"]),
                "author_uuid": self._uuid_to_str(row["author_uuid"]),
                "created_at": row["created_at"],
                "created_by_run": self._uuid_to_str(row["created_by_run"]),
            }
            output_items.append((url, metadata))

        return output_items

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

        # 1. Filter rows with text
        candidates = messages_table.filter(messages_table.text.notnull())

        # Patterns
        # Markdown Links & Images: [...](url) -> group 1
        # Captures both ![alt](url) and [text](url)
        md_pattern = r"\[(?:[^\]]*)\]\(([^)]+)\)"

        # Plain Filename: \b([\w\-\.]+\.\w{2,})\b -> group 0 (full match)
        # We capture group 0 by passing 0 to regexp_extract_all
        plain_file_pattern = r"\b([\w\-\.]+\.\w{2,})\b"

        cols = [
            "ts",
            "event_id",
            "tenant_id",
            "source",
            "thread_id",
            "author_uuid",
            "created_at",
            "created_by_run",
        ]

        # Helper to construct candidate sets
        def _extract_candidates(pattern: str, group: int) -> Table:
            q = candidates.mutate(filenames=regexp_extract_all(candidates.text, pattern, group))
            return q.select(filename=q.filenames.unnest(), **{c: q[c] for c in cols})

        # Set 1: Markdown References (Images & Links)
        q1 = _extract_candidates(md_pattern, 1)

        # Set 2: Plain Filenames
        q2 = _extract_candidates(plain_file_pattern, 0)

        # Combine all sets
        combined = q1.union(q2)

        # Post-processing: Extract filename from path (e.g., path/to/image.jpg -> image.jpg)
        filename_only_pattern = r"([^/]+)$"
        combined = combined.mutate(clean_filename=combined.filename.re_extract(filename_only_pattern, 1))
        combined = combined.mutate(clean_filename=ibis.coalesce(combined.clean_filename, combined.filename))

        # Filter out invalid TLDs (heuristics from find_all_media_references)
        ext_pattern = r"\.([^.]+)$"
        combined = combined.mutate(ext=combined.clean_filename.re_extract(ext_pattern, 1).lower())
        ignored_tlds = ("com", "org", "net", "io", "co", "de", "fr", "uk")
        combined = combined.filter(~combined.ext.isin(ignored_tlds))

        # Deduplicate: Keep earliest timestamp for each filename
        w = ibis.window(group_by="clean_filename", order_by="ts")
        combined = combined.mutate(rank=ibis.row_number().over(w))
        combined = combined.filter(combined.rank == 0)

        # Limit and Sort
        combined = combined.order_by(["ts", "clean_filename"]).limit(limit)

        try:
            results = combined.execute()
        except Exception:
            logger.exception("Failed to execute media enrichment query")
            return []

        output_items = []
        for row in results.to_dict("records"):
            ref = row["clean_filename"]
            if not ref:
                continue

            metadata = {
                "ts": ensure_datetime(row["ts"]) if row["ts"] else None,
                "event_id": self._uuid_to_str(row["event_id"]),
                "tenant_id": row["tenant_id"],
                "source": row["source"],
                "thread_id": self._uuid_to_str(row["thread_id"]),
                "author_uuid": self._uuid_to_str(row["author_uuid"]),
                "created_at": row["created_at"],
                "created_by_run": self._uuid_to_str(row["created_by_run"]),
            }

            doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, ref))
            doc = Document(
                content=b"",
                type=DocumentType.MEDIA,
                id=doc_id,
                metadata={
                    "filename": ref,
                    "original_filename": ref,
                    "media_type": mimetypes.guess_type(ref)[0] or "application/octet-stream",
                },
            )
            output_items.append((ref, doc, metadata))

        return output_items
