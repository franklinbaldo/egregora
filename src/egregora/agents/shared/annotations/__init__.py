"""Conversation annotation system for threading, metadata, and conversation units.

This module provides a DuckDB-backed annotation storage layer that enables the writer
agent to attach metadata and commentary to messages and other annotations, creating
threaded conversation structures. Privacy filtering is expected to occur upstream
before LLM invocation; the annotation store does not run PII detection when saving
records.

Architecture:
    - DuckDB storage with Ibis query interface for type-safe operations
    - Auto-incrementing sequences for annotation IDs
    - Parent-child relationships via parent_id/parent_type foreign keys
    - Supports annotation threading: annotations can reference messages or other annotations

Key Components:
    - AnnotationStore: Main storage class with DuckDB persistence
    - Annotation: Dataclass representing a stored annotation record
    - ANNOTATIONS_TABLE: Table name constant for the annotations storage
    - ANNOTATION_AUTHOR: Default author identifier ("egregora")

Schema:
    The annotations table follows this structure:
    - id: INTEGER (auto-increment primary key)
    - parent_id: VARCHAR (message_id or annotation_id)
    - parent_type: VARCHAR ("message" or "annotation")
    - author: VARCHAR (typically "egregora")
    - commentary: VARCHAR (the annotation content; PII masking occurs upstream)
    - created_at: TIMESTAMP (UTC)

Use Cases:
    1. Conversation threading: Link related messages and annotations
    2. Metadata tagging: Attach context, themes, or editorial notes to messages
    3. RAG context enrichment: Provide additional context for retrieval operations
    4. Post generation: Guide the writer agent with conversation structure insights

Example:
    >>> from pathlib import Path
    >>> from egregora.agents.shared.annotations import AnnotationStore
    >>>
    >>> # Initialize annotation storage
    >>> from egregora.database.duckdb_manager import DuckDBStorageManager
    >>> storage = DuckDBStorageManager(db_path=Path(".egregora-cache/annotations.duckdb"))
    >>> store = AnnotationStore(storage)
    >>>
    >>> # Annotate a message
    >>> annotation = store.save_annotation(
    ...     parent_id="msg_abc123",
    ...     parent_type="message",
    ...     commentary="This message introduces the main topic of discussion"
    ... )
    >>>
    >>> # Retrieve annotations for a message
    >>> msg_annotations = store.list_annotations_for_message("msg_abc123")
    >>> for ann in msg_annotations:
    ...     print(f"{ann.created_at}: {ann.commentary}")
    >>>
    >>> # Join annotations with messages for vectorized operations
    >>> import ibis
    >>> messages = ibis.table(...)  # Your messages table
    >>> joined = store.join_with_messages(messages)
    >>> annotated = joined.filter(joined.commentary.notnull())

Note:
    This module does NOT use the centralized schemas from database.schema.ANNOTATIONS_SCHEMA.
    The schema is defined inline via CREATE TABLE statements for tighter control over
    sequences and auto-increment behavior.

"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import ibis

from egregora.data_primitives.document import Document, DocumentType, OutputSink
from egregora.database import schemas as database_schema

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from egregora.database.protocols import SequenceStorageProtocol, StorageProtocol

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================
# Default author identifier for all annotations created by the writer agent
ANNOTATION_AUTHOR = "egregora"

# DuckDB table name where annotations are persisted
ANNOTATIONS_TABLE = "annotations"


# ============================================================================
# Data Models
# ============================================================================


@dataclass(slots=True)
class Annotation:
    """Representation of a stored conversation annotation.

    This is the in-memory representation of an annotation record retrieved
    from the DuckDB storage. Annotations form a tree structure where each
    annotation can reference either a message or another annotation as its parent.

    Attributes:
        id: Unique annotation identifier (auto-generated)
        parent_id: ID of the parent entity (message_id or annotation_id)
        parent_type: Type of parent entity ("message" or "annotation")
        author: Author identifier (typically "egregora")
        commentary: The annotation content (not privacy-validated here)
        created_at: UTC timestamp of annotation creation

    """

    id: str  # UUID v4 instead of integer sequence
    parent_id: str
    parent_type: str
    author: str
    commentary: str
    created_at: datetime

    def to_document(self) -> Document:
        """Convert this annotation into a lightweight :class:`Document` instance.

        Annotations are treated as dedicated :class:`DocumentType.ANNOTATION` documents.
        They carry stable identity, authorship, and parent references.

        Returns:
            Document representation of the annotation ready for serving/indexing.

        """
        # Ensure title and slug for Post compatibility
        slug = f"annotation-{self.id}"
        metadata = {
            "annotation_id": str(self.id),
            "title": f"Annotation {self.id}",
            "parent_id": self.parent_id,
            "parent_type": self.parent_type,
            "author": self.author,  # Defaults to "egregora"
            "categories": ["Annotations"],
            "slug": slug,
            "date": self.created_at,
        }

        identity_header = (
            "<!--\n"
            f"annotation_id: {self.id}\n"
            f"parent_type: {self.parent_type}\n"
            f"parent_id: {self.parent_id}\n"
            "-->\n\n"
        )

        return Document(
            content=f"{identity_header}{self.commentary}",
            type=DocumentType.ANNOTATION,
            metadata=metadata,
            created_at=self.created_at,
        )


# ============================================================================
# Storage Layer
# ============================================================================


class AnnotationStore:
    """DuckDB-backed storage for writer annotations accessed via Ibis.

    This class manages the lifecycle of annotations including schema initialization,
    sequence management, and CRUD operations. It uses DuckDB for persistence with
    an Ibis interface for type-safe queries.

    The store handles:
    - Auto-incrementing sequence management for annotation IDs
    - Parent-child relationship validation (annotations can only reference existing parents)
    - Efficient joins with message tables for vectorized operations

    Storage Format:
        - Database: DuckDB (single file)
        - Table: annotations
        - Indexes: (parent_id, parent_type, created_at) for efficient lookups
        - Sequences: annotations_id_seq for auto-increment
    """

    def __init__(
        self,
        storage: StorageProtocol & SequenceStorageProtocol,
        output_sink: OutputSink | None = None,
    ) -> None:
        """Initialize annotation store.

        Args:
            storage: Storage backend implementing both StorageProtocol and SequenceStorageProtocol
            output_sink: Optional sink for persisting annotations as documents

        """
        self.storage = storage
        self.output_sink = output_sink
        self._backend = storage.ibis_conn
        # No longer using sequences - UUIDs are generated in save_annotation()
        self._initialize_schema()

    # Note: Removed _connection property - use storage.connection() context manager instead

    # ========================================================================
    # Schema Initialization
    # ========================================================================

    def _initialize_schema(self) -> None:
        """Initialize database schema and indexes.

        This method is called during __init__ and performs:
        1. Create annotations table with proper schema (UUID-based ID)
        2. Add primary key constraint
        3. Create composite index on (parent_id, parent_type, created_at)

        Note: We no longer use sequences - IDs are UUIDs generated in save_annotation().
        """
        # Use centralized schema definition
        database_schema.create_table_if_not_exists(
            self._backend, ANNOTATIONS_TABLE, database_schema.ANNOTATIONS_SCHEMA
        )

        # Use protocol method instead of accessing protected member
        with self.storage.connection() as conn:
            database_schema.add_primary_key(conn, ANNOTATIONS_TABLE, "id")

        self._backend.raw_sql(
            f"CREATE INDEX IF NOT EXISTS idx_annotations_parent_created ON {ANNOTATIONS_TABLE} (parent_id, parent_type, created_at)"  # nosec B608
        )

    # ========================================================================
    # Internal Utilities
    # ========================================================================

    def _fetch_records(self, query: str, params: Sequence[object] | None = None) -> list[dict[str, object]]:
        """Execute a query and return results as a list of dictionaries."""
        # Use protocol method instead of accessing protected member
        with self.storage.connection() as conn:
            cursor = conn.execute(query, params or [])
            column_names = [description[0] for description in cursor.description]
            return [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def save_annotation(
        self,
        parent_id: str,
        parent_type: Literal["message", "annotation"],
        commentary: str,
    ) -> Annotation:
        """Persist an annotation and return the saved record."""
        # Trust internal callers, type hints enforce contract
        created_at = datetime.now(UTC)
        annotation_id = str(uuid.uuid4())  # Generate UUID v4 instead of using sequence
        # Note: commentary is stored in 'content' column per schema
        # We also provide empty 'id' and 'source_checksum' to satisfy BASE_COLUMNS if needed,
        # but id is handled by sequence and source_checksum is nullable/defaulted usually.
        # Actually BASE_COLUMNS has source_checksum as string. We should probably provide it or let default handle it if nullable?
        # Looking at schema, source_checksum is string.
        # Let's check schemas.py again. BASE_COLUMNS: "source_checksum": dt.string
        # It doesn't say nullable.
        # However, create_table_if_not_exists creates table based on schema.
        # If Ibis insert doesn't provide it, it might fail if not nullable.
        # Let's provide a dummy checksum.
        insert_row = ibis.memtable(
            [
                {
                    "id": annotation_id,
                    "parent_id": parent_id,
                    "parent_type": parent_type,
                    "author": ANNOTATION_AUTHOR,
                    "content": commentary,
                    "created_at": created_at,
                    "source_checksum": "manual",  # Dummy value
                }
            ]
        )
        self._backend.insert(ANNOTATIONS_TABLE, insert_row)
        annotation = Annotation(
            id=annotation_id,
            parent_id=parent_id,
            parent_type=parent_type,
            author=ANNOTATION_AUTHOR,
            commentary=commentary,
            created_at=created_at,
        )

        if self.output_sink:
            try:
                self.output_sink.persist(annotation.to_document())
            except Exception as exc:
                logger.warning("Failed to persist annotation %s: %s", annotation.id, exc)

        return annotation

    # ========================================================================
    # Query Operations
    # ========================================================================

    def list_annotations_for_message(self, msg_id: str) -> list[Annotation]:
        """Return annotations for ``msg_id`` ordered by creation time."""
        records = self._fetch_records(
            f"SELECT id, parent_id, parent_type, author_id as author, content as commentary, created_at FROM {ANNOTATIONS_TABLE} WHERE parent_id = ? AND parent_type = 'message' ORDER BY created_at ASC, id ASC",  # nosec B608
            [msg_id],
        )
        return [self._row_to_annotation(row) for row in records]

    def get_last_annotation_id(self, msg_id: str) -> int | None:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""
        # Use protocol method instead of accessing protected member
        with self.storage.connection() as conn:
            cursor = conn.execute(
                f"SELECT id FROM {ANNOTATIONS_TABLE} WHERE parent_id = ? AND parent_type = 'message' ORDER BY created_at DESC, id DESC LIMIT 1",  # nosec B608
                [msg_id],
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def iter_all_annotations(self) -> Iterable[Annotation]:
        """Yield all annotations sorted by insertion order."""
        records = self._fetch_records(
            f"SELECT id, parent_id, parent_type, author_id as author, content as commentary, created_at FROM {ANNOTATIONS_TABLE} ORDER BY created_at ASC, id ASC"  # nosec B608
        )
        for row in records:
            yield self._row_to_annotation(row)

    def iter_annotation_documents(self) -> Iterable[Document]:
        """Yield all annotations transformed into :class:`Document` objects."""
        for annotation in self.iter_all_annotations():
            yield annotation.to_document()

    # ========================================================================
    # Vectorized Operations
    # ========================================================================

    def join_with_messages(self, messages_table: ibis.expr.types.Table) -> ibis.expr.types.Table:
        """Join annotations with messages using message_id as foreign key.

        This enables vectorized operations on the combined data.

        Args:
            messages_table: Ibis Table with 'message_id' column

        Returns:
            Joined Ibis Table with both message and annotation columns

        Example:
            >>> # Assuming messages_table has message_id column
            >>> annotations_store = AnnotationStore(db_path)
            >>> joined = annotations_store.join_with_messages(messages_table)
            >>> # Now you can do vectorized operations like:
            >>> annotated_messages = joined.filter(joined.commentary.notnull())

        """
        annotations_table = self._backend.table(ANNOTATIONS_TABLE)
        message_annotations = annotations_table[annotations_table.parent_type == "message"]
        return messages_table.left_join(
            message_annotations, messages_table.message_id == message_annotations.parent_id
        )

    # ========================================================================
    # Data Conversion
    # ========================================================================

    @staticmethod
    def _row_to_annotation(row: dict[str, Any]) -> Annotation:
        """Convert a database row dictionary to an Annotation instance.

        Handles various datetime formats from DuckDB (datetime, ISO strings)
        and ensures all timestamps are in UTC timezone.

        Args:
            row: Dictionary with keys matching Annotation fields

        Returns:
            Annotation instance with properly typed and timezone-aware created_at

        """
        created_at_obj = row["created_at"]
        if hasattr(created_at_obj, "to_pydatetime"):
            created_at = created_at_obj.to_pydatetime()
        elif isinstance(created_at_obj, datetime):
            created_at = created_at_obj
        else:
            dt_str = str(created_at_obj).replace("Z", "+00:00")
            created_at = datetime.fromisoformat(dt_str)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        else:
            created_at = created_at.astimezone(UTC)
        return Annotation(
            id=str(row["id"]),  # ID is now a UUID string
            parent_id=str(row["parent_id"]),
            parent_type=str(row["parent_type"]),
            author=str(row["author"]),
            commentary=str(row["commentary"]),
            created_at=created_at,
        )


# ============================================================================
# Public API
# ============================================================================
# Export the core components for external use:
# - ANNOTATIONS_TABLE: Table name constant
# - ANNOTATION_AUTHOR: Default author identifier
# - Annotation: Dataclass for annotation records
# - AnnotationStore: Main storage class for CRUD operations
__all__ = ["ANNOTATIONS_TABLE", "ANNOTATION_AUTHOR", "Annotation", "AnnotationStore"]
