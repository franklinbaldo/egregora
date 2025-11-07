"""Conversation annotation system for threading, metadata, and conversation units.

This module provides a DuckDB-backed annotation storage layer that enables the writer
agent to attach metadata and commentary to messages and other annotations, creating
threaded conversation structures.

Architecture:
    - DuckDB storage with Ibis query interface for type-safe operations
    - Auto-incrementing sequences for annotation IDs
    - Parent-child relationships via parent_id/parent_type foreign keys
    - Privacy validation: all commentary is checked for PII before persistence
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
    - commentary: VARCHAR (the annotation content, PII-checked)
    - created_at: TIMESTAMP (UTC)

Use Cases:
    1. Conversation threading: Link related messages and annotations
    2. Metadata tagging: Attach context, themes, or editorial notes to messages
    3. RAG context enrichment: Provide additional context for retrieval operations
    4. Post generation: Guide the writer agent with conversation structure insights

Example:
    >>> from pathlib import Path
    >>> from egregora.agents.tools.annotations import AnnotationStore
    >>>
    >>> # Initialize annotation storage
    >>> store = AnnotationStore(Path(".egregora-cache/annotations.duckdb"))
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

Privacy & Security:
    All commentary is validated against PII patterns before persistence using
    validate_newsletter_privacy() to ensure no personal information leaks into
    the annotation storage.

Note:
    This module does NOT use the centralized schemas from database.schema.ANNOTATIONS_SCHEMA.
    The schema is defined inline via CREATE TABLE statements for tighter control over
    sequences and auto-increment behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ibis

from egregora.database import schema as database_schema
from egregora.privacy.detector import PrivacyViolationError, validate_newsletter_privacy

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    import duckdb

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
        commentary: The annotation content (validated for PII)
        created_at: UTC timestamp of annotation creation
    """

    id: int
    parent_id: str
    parent_type: str
    author: str
    commentary: str
    created_at: datetime


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
    - Privacy validation via PII detection before persistence
    - Parent-child relationship validation (annotations can only reference existing parents)
    - Efficient joins with message tables for vectorized operations

    Storage Format:
        - Database: DuckDB (single file)
        - Table: annotations
        - Indexes: (parent_id, parent_type, created_at) for efficient lookups
        - Sequences: annotations_id_seq for auto-increment
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = ibis.duckdb.connect(str(self.db_path))
        self._initialize()

    @property
    def _connection(self) -> duckdb.DuckDBPyConnection:
        """Return the underlying DuckDB connection."""
        return self._backend.con

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
        sequence_name = f"{ANNOTATIONS_TABLE}_id_seq"
        self._connection.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name} START 1")
        self._connection.execute(
            f"\n            CREATE TABLE IF NOT EXISTS {ANNOTATIONS_TABLE} (\n                id INTEGER PRIMARY KEY DEFAULT nextval('{sequence_name}'),\n                parent_id VARCHAR NOT NULL,\n                parent_type VARCHAR NOT NULL,\n                author VARCHAR,\n                commentary VARCHAR,\n                created_at TIMESTAMP\n            )\n            "
        )
        database_schema.add_primary_key(self._connection, ANNOTATIONS_TABLE, "id")
        column_default_row = self._connection.execute(
            "\n            SELECT column_default\n            FROM information_schema.columns\n            WHERE lower(table_name) = lower(?) AND lower(column_name) = 'id'\n            LIMIT 1\n            ",
            [ANNOTATIONS_TABLE],
        ).fetchone()
        if not column_default_row or column_default_row[0] != f"nextval('{sequence_name}')":
            self._connection.execute(
                f"ALTER TABLE {ANNOTATIONS_TABLE} ALTER COLUMN id SET DEFAULT nextval('{sequence_name}')"
            )
        self._backend.raw_sql(
            f"\n            CREATE INDEX IF NOT EXISTS idx_annotations_parent_created\n            ON {ANNOTATIONS_TABLE} (parent_id, parent_type, created_at)\n            "
        )
        max_id_row = self._connection.execute(f"SELECT MAX(id) FROM {ANNOTATIONS_TABLE}").fetchone()
        if max_id_row and max_id_row[0] is not None:
            max_id = int(max_id_row[0])
            sequence_state = self._connection.execute(
                "\n                SELECT start_value, increment_by, last_value\n                FROM duckdb_sequences()\n                WHERE schema_name = current_schema() AND sequence_name = ?\n                LIMIT 1\n                ",
                [sequence_name],
            ).fetchone()
            if sequence_state is None:
                msg = f"Could not find sequence metadata for {sequence_name}"
                raise RuntimeError(msg)
            start_value, increment_by, last_value = sequence_state
            current_next = int(start_value) if last_value is None else int(last_value) + int(increment_by)
            desired_next = max(current_next, max_id + 1)
            steps_needed = desired_next - current_next
            if steps_needed > 0:
                cursor = self._connection.execute(
                    "SELECT nextval(?) FROM range(?)", [sequence_name, steps_needed]
                )
                cursor.fetchall()

    # ========================================================================
    # Internal Utilities
    # ========================================================================

    def _fetch_records(self, query: str, params: Sequence[object] | None = None) -> list[dict[str, object]]:
        """Execute a query and return results as a list of dictionaries."""
        cursor = self._connection.execute(query, params or [])
        column_names = [description[0] for description in cursor.description]
        return [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]

    # ========================================================================
    # CRUD Operations
    # ========================================================================

    def save_annotation(self, parent_id: str, parent_type: str, commentary: str) -> Annotation:
        """Persist an annotation and return the saved record."""
        sanitized_parent_id = (parent_id or "").strip()
        sanitized_parent_type = (parent_type or "").strip().lower()
        sanitized_commentary = (commentary or "").strip()
        if not sanitized_parent_id:
            msg = "parent_id is required"
            raise ValueError(msg)
        if sanitized_parent_type not in ("message", "annotation"):
            msg = "parent_type must be 'message' or 'annotation'"
            raise ValueError(msg)
        if not sanitized_commentary:
            msg = "commentary must not be empty"
            raise ValueError(msg)
        try:
            validate_newsletter_privacy(sanitized_commentary)
        except PrivacyViolationError as exc:
            raise ValueError(str(exc)) from exc
        created_at = datetime.now(UTC)
        if sanitized_parent_type == "annotation":
            annotations_table = self._backend.table(ANNOTATIONS_TABLE)
            parent_exists = int(
                annotations_table.filter(annotations_table.id == int(sanitized_parent_id))
                .limit(1)
                .count()
                .execute()
            )
            if parent_exists == 0:
                msg = f"parent annotation with id {sanitized_parent_id} does not exist"
                raise ValueError(msg)
        cursor = self._connection.execute(
            f"\n            INSERT INTO {ANNOTATIONS_TABLE} (parent_id, parent_type, author, commentary, created_at)\n            VALUES (?, ?, ?, ?, ?)\n            RETURNING id\n            ",
            [sanitized_parent_id, sanitized_parent_type, ANNOTATION_AUTHOR, sanitized_commentary, created_at],
        )
        row = cursor.fetchone()
        if row is None:
            msg = "Could not insert annotation"
            raise RuntimeError(msg)
        annotation_id = int(row[0])
        return Annotation(
            id=annotation_id,
            parent_id=sanitized_parent_id,
            parent_type=sanitized_parent_type,
            author=ANNOTATION_AUTHOR,
            commentary=sanitized_commentary,
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
            f"\n            SELECT id, parent_id, parent_type, author, commentary, created_at\n            FROM {ANNOTATIONS_TABLE}\n            WHERE parent_id = ? AND parent_type = 'message'\n            ORDER BY created_at ASC, id ASC\n            ",
            [sanitized_msg_id],
        )
        return [self._row_to_annotation(row) for row in records]

    def get_last_annotation_id(self, msg_id: str) -> int | None:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""
        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return None
        cursor = self._connection.execute(
            f"\n            SELECT id FROM {ANNOTATIONS_TABLE}\n            WHERE parent_id = ? AND parent_type = 'message'\n            ORDER BY created_at DESC, id DESC\n            LIMIT 1\n            ",
            [sanitized_msg_id],
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    def iter_all_annotations(self) -> Iterable[Annotation]:
        """Yield all annotations sorted by insertion order."""
        records = self._fetch_records(
            f"\n            SELECT id, parent_id, parent_type, author, commentary, created_at\n            FROM {ANNOTATIONS_TABLE}\n            ORDER BY created_at ASC, id ASC\n            "
        )
        for row in records:
            yield self._row_to_annotation(row)

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
