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
from egregora.ops.media import MEDIA_EXTENSIONS

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

    def _get_media_candidates_vectorized(
        self, messages_table: Table, limit: int
    ) -> list[tuple[str, Any, dict[str, Any]]]:
        """Vectorized implementation of media candidate extraction."""
        # 0. Base filter: messages with text
        t = messages_table.filter(messages_table.text.notnull())

        # Define regex patterns
        # 1. Markdown refs (Links & Images): [alt](url) -> extract url/filename
        # Logic: Extract the part after the last slash inside parentheses
        # Regex: \[.*?\]\((?:.*?/)?([^/)]+)\)
        # Matches both ![img](...) and [link](...)
        re_markdown = r"\[.*?\]\((?:.*?/)?([^/)]+)\)"

        # 2. WhatsApp/Unicode: (IMG|VID...)-...
        re_wa = r"((?:IMG|VID|AUD|PTT|DOC)-\d+-WA\d+\.\w+)"

        # 3. Attachment markers: filename followed by marker
        # We capture the filename group (1)
        re_attachment = r"([\w\-\.]+\.\w+)\s*(?:\(file attached\)|\(arquivo anexado\)|<attached:)"

        # 4. Plain filenames: word characters, dots, min 2 char extension
        re_plain = r"\b([\w\-\.]+\.\w{2,})\b"

        # 5. UUIDs: 8-4-4-4-12 hex, optional extension
        re_uuid = r"\b([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}(?:\.\w+)?)\b"

        # Extract streams
        # Using group=1 for those that have capture groups we want
        # For UUID/WA, the whole match is group 1 because we wrapped it in ()

        def extract_stream(pattern: str, source_type: str, group: int = 1) -> Table:
            return t.select(
                ref=regexp_extract_all(t.text, pattern, group).unnest(),
                ts=t.ts,
                media_type=t.media_type,
                event_id=t.event_id,
                tenant_id=t.tenant_id,
                source=t.source,
                thread_id=t.thread_id,
                author_uuid=t.author_uuid,
                created_at=t.created_at,
                created_by_run=t.created_by_run,
                source_type=ibis.literal(source_type),
            )

        s1 = extract_stream(re_markdown, "markdown")
        s2 = extract_stream(re_wa, "wa")
        s3 = extract_stream(re_attachment, "attachment")
        s4 = extract_stream(re_plain, "plain")
        s5 = extract_stream(re_uuid, "uuid")

        # Union all streams
        candidates = s1.union(s2).union(s3).union(s4).union(s5)

        # Filters
        # 1. Plain source: Exclude blacklist domains
        blacklist = ("com", "org", "net", "io", "co", "de", "fr", "uk")
        # Extract extension: split by dot, take last
        # Note: ibis string split returns array.
        ext_col = candidates.ref.split(".")
        ext = ext_col[ext_col.length() - 1].lower()

        # Filter for 'plain' source: must not be in blacklist AND must not look like UUID
        # We check UUID lookalike by re-matching UUID pattern on the ref
        is_uuid_lookalike = candidates.ref.re_search(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\."
        )

        candidates = candidates.filter(
            ~((candidates.source_type == "plain") & (ext.isin(blacklist) | is_uuid_lookalike))
        )

        # 2. UUID source: Filter based on media_type logic
        # Logic: If media_type is truthy (e.g. 'URL', 'Media', or just not null/empty), keep all UUIDs.
        # If media_type is falsy/null, keep only UUIDs with known extensions.
        # Check known extensions
        known_exts = tuple(MEDIA_EXTENSIONS.keys())  # e.g. ('.jpg', '.png'...)
        # We need to check if ref ends with any of these.
        # Or simpler: extract extension with dot and check IsIn.
        # ext variable above is without dot.
        # Let's reconstruct extension with dot: '.' + ext
        # But ext calculation assumes there IS a dot. UUIDs might not have one.

        has_ext = candidates.ref.contains(".")
        # If has_ext, ext is valid.

        # Need to fix ext extraction to be safe if no dot
        # If no dot, split returns 1 element (the string). ext is the string.
        # But we only care about extensions for filtering.

        ref_dot_ext = "." + ext
        is_known_ext = has_ext & ref_dot_ext.isin(known_exts)

        # media_type is often String. Empty string is falsy in Python but distinct from NULL in SQL.
        # logic: bool(row.get("media_type")) -> True if not None and not empty.
        media_type_truthy = candidates.media_type.notnull() & (candidates.media_type != "")

        candidates = candidates.filter(
            ~((candidates.source_type == "uuid") & (~media_type_truthy & ~is_known_ext))
        )

        # 4. Deduplicate (Keep earliest)
        w = ibis.window(group_by="ref", order_by="ts")
        candidates = candidates.mutate(rank=ibis.row_number().over(w))
        candidates = candidates.filter(candidates.rank == 0)

        # 5. Limit
        candidates = candidates.order_by(["ts", "ref"]).limit(limit)

        # Execute
        try:
            results = candidates.execute()
        except Exception:
            logger.exception("Vectorized media extraction failed")
            return []

        # Map to output format
        output = []
        for row in results.to_dict("records"):
            ref = row["ref"]

            # Reconstruct metadata
            meta = {
                "ts": ensure_datetime(row["ts"]) if row["ts"] else None,
                "event_id": self._uuid_to_str(row["event_id"]),
                "tenant_id": row["tenant_id"],
                "source": row["source"],
                "thread_id": self._uuid_to_str(row["thread_id"]),
                "author_uuid": self._uuid_to_str(row["author_uuid"]),
                "created_at": row["created_at"],
                "created_by_run": self._uuid_to_str(row["created_by_run"]),
            }

            # Reconstruct Document
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

            output.append((ref, doc, meta))

        return output

    def get_media_enrichment_candidates(
        self, messages_table: Table, media_mapping: dict, limit: int
    ) -> list[tuple[str, Any, dict[str, Any]]]:
        """Extract unique Media candidates with metadata."""
        if limit <= 0:
            return []

        # Use vectorized implementation
        return self._get_media_candidates_vectorized(messages_table, limit)
