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

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

import ibis

from egregora.data_primitives.document import Document, DocumentType
from egregora.database import ir_schema as database_schema

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import duckdb

    from egregora.database.protocols import SequenceStorageProtocol, StorageProtocol

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

    id: int
    parent_id: str
    parent_type: str
    author: str
    commentary: str
    created_at: datetime

    def to_document(self) -> Document:
        """Convert this annotation into a lightweight :class:`Document` instance.

        Annotations already carry stable identity, authorship, and parent references.
        Exposing them as documents lets downstream components (output adapters,
        enrichment pipelines, retrieval) treat annotations just like any other
        publishable content without special cases.

        Returns:
            Document representation of the annotation ready for serving/indexing.

        """
        metadata = {
            "annotation_id": str(self.id),
            "title": f"Annotation {self.id}",
            "parent_id": self.parent_id,
            "parent_type": self.parent_type,
            "author": self.author,
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

    def __init__(self, storage: StorageProtocol & SequenceStorageProtocol) -> None:  # type: ignore[misc]
        """Initialize annotation store.

        Args:
            storage: Storage backend implementing both StorageProtocol and SequenceStorageProtocol

        """
        self.storage = storage
        self._backend = storage.ibis_conn
        self._sequence_name = f"{ANNOTATIONS_TABLE}_id_seq"
        self._initialize()

    # Note: Removed _connection property - use storage.connection() context manager instead

    # ========================================================================
    # Schema Initialization
    # ========================================================================

    def _initialize(self) -> None:
        """Initialize database schema, sequences, and indexes.

        This method is called during __init__ and performs:
        1. Create auto-increment sequence for annotation IDs
        2. Create annotations table with proper schema
        3. Add primary key constraint
        4. Set default value for id column to use sequence
        5. Create composite index on (parent_id, parent_type, created_at)
        6. Sync sequence state with existing data (handles database restarts)

        The sequence synchronization ensures that if the database already contains
        annotations, the sequence starts at max(id) + 1 to avoid conflicts.
        """
        sequence_name = self._sequence_name
        self.storage.ensure_sequence(sequence_name)
        # Use centralized schema definition
        database_schema.create_table_if_not_exists(
            self._backend, ANNOTATIONS_TABLE, database_schema.ANNOTATIONS_SCHEMA
        )
        # Manually alter ID to use sequence (ibis create_table doesn't support DEFAULT nextval yet)
        self._backend.raw_sql(
            f"ALTER TABLE {ANNOTATIONS_TABLE} ALTER COLUMN id SET DEFAULT nextval('{sequence_name}')"
        )
        # Use protocol method instead of accessing protected member
        with self.storage.connection() as conn:
            database_schema.add_primary_key(conn, ANNOTATIONS_TABLE, "id")
        self.storage.ensure_sequence_default(ANNOTATIONS_TABLE, "id", sequence_name)
        self._backend.raw_sql(
            f"\n            CREATE INDEX IF NOT EXISTS idx_annotations_parent_created\n            ON {ANNOTATIONS_TABLE} (parent_id, parent_type, created_at)\n            "
        )
        self.storage.sync_sequence_with_table(sequence_name, table=ANNOTATIONS_TABLE, column="id")

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
        # Runtime privacy check
        # TODO: Re-enable when egregora.privacy.pii module is implemented
        # from egregora.privacy.config import PrivacySettings
        #
        # if PrivacySettings.detect_pii:
        #     from egregora.privacy.pii import detect_pii
        #
        #     if detect_pii(commentary):
        #         msg = "Annotation commentary contains PII"
        #         raise ValueError(msg)

        created_at = datetime.now(UTC)
        if parent_type == "annotation":
            annotations_table = self._backend.table(ANNOTATIONS_TABLE)
            parent_exists = int(
                annotations_table.filter(annotations_table.id == int(parent_id)).limit(1).count().execute()
            )
            if parent_exists == 0:
                msg = f"parent annotation with id {parent_id} does not exist"
                raise ValueError(msg)
        annotation_id = self.storage.next_sequence_value(self._sequence_name)
        insert_row = ibis.memtable(
            [
                {
                    "id": annotation_id,
                    "parent_id": parent_id,
                    "parent_type": parent_type,
                    "author": ANNOTATION_AUTHOR,
                    "commentary": commentary,
                    "created_at": created_at,
                }
            ]
        )
        self._backend.insert(ANNOTATIONS_TABLE, insert_row)
        return Annotation(
            id=annotation_id,
            parent_id=parent_id,
            parent_type=parent_type,
            author=ANNOTATION_AUTHOR,
            commentary=commentary,
            created_at=created_at,
        )

    # ========================================================================
    # Query Operations
    # ========================================================================

    def list_annotations_for_message(self, msg_id: str) -> list[Annotation]:
        """Return annotations for ``msg_id`` ordered by creation time."""
        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return []
        records = self._fetch_records(
            f"\n            SELECT id, parent_id, parent_type, author, commentary, created_at\n            FROM {ANNOTATIONS_TABLE}\n            WHERE parent_id = ? AND parent_type = 'message'\n            ORDER BY created_at ASC, id ASC\n            ",  # nosec B608 - ANNOTATIONS_TABLE is module constant
            [sanitized_msg_id],
        )
        return [self._row_to_annotation(row) for row in records]

    def get_last_annotation_id(self, msg_id: str) -> int | None:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""
        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return None
        # Use protocol method instead of accessing protected member
        with self.storage.connection() as conn:
            cursor = conn.execute(
                f"\n            SELECT id FROM {ANNOTATIONS_TABLE}\n            WHERE parent_id = ? AND parent_type = 'message'\n            ORDER BY created_at DESC, id DESC\n            LIMIT 1\n            ",  # nosec B608 - ANNOTATIONS_TABLE is module constant
                [sanitized_msg_id],
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None

    def iter_all_annotations(self) -> Iterable[Annotation]:
        """Yield all annotations sorted by insertion order."""
        records = self._fetch_records(
            f"\n            SELECT id, parent_id, parent_type, author, commentary, created_at\n            FROM {ANNOTATIONS_TABLE}\n            ORDER BY created_at ASC, id ASC\n            "  # nosec B608 - ANNOTATIONS_TABLE is module constant
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

        Handles various datetime formats from DuckDB (pandas Timestamp, datetime, ISO strings)
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
            id=int(row["id"]),
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
