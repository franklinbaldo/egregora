"""Persistence layer for writer conversation annotations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import ibis

from ..core import database_schema
from ..privacy.detector import PrivacyViolationError, validate_newsletter_privacy

ANNOTATION_AUTHOR = "egregora"
ANNOTATIONS_TABLE = "annotations"


@dataclass(slots=True)
class Annotation:
    """Representation of a stored conversation annotation."""

    id: int
    parent_id: str
    parent_type: str
    author: str
    commentary: str
    created_at: datetime


class AnnotationStore:
    """DuckDB-backed storage for writer annotations accessed via Ibis."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = ibis.duckdb.connect(str(self.db_path))
        self._initialize()

    @property
    def _connection(self) -> duckdb.DuckDBPyConnection:
        """Return the underlying DuckDB connection."""

        return self._backend.con

    def _initialize(self) -> None:
        self._connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {ANNOTATIONS_TABLE} (
                id BIGINT PRIMARY KEY,
                parent_id VARCHAR NOT NULL,
                parent_type VARCHAR NOT NULL,
                author VARCHAR,
                commentary VARCHAR,
                created_at TIMESTAMP
            )
            """
        )
        try:
            self._connection.execute(
                f"ALTER TABLE {ANNOTATIONS_TABLE} ALTER COLUMN id DROP DEFAULT"
            )
        except duckdb.Error:
            # Default may already be absent or incompatible with DROP DEFAULT
            pass
        database_schema.ensure_identity_column(
            self._connection, ANNOTATIONS_TABLE, "id", generated="ALWAYS"
        )
        # Add primary key using raw connection
        database_schema.add_primary_key(self._connection, ANNOTATIONS_TABLE, "id")
        self._backend.raw_sql(
            f"""
            CREATE INDEX IF NOT EXISTS idx_annotations_parent_created
            ON {ANNOTATIONS_TABLE} (parent_id, parent_type, created_at)
            """
        )

    def _fetch_records(
        self, query: str, params: Sequence[object] | None = None
    ) -> list[dict[str, object]]:
        cursor = self._connection.execute(query, params or [])
        column_names = [description[0] for description in cursor.description]
        return [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]

    def save_annotation(
        self,
        parent_id: str,
        parent_type: str,
        commentary: str,
    ) -> Annotation:
        """Persist an annotation and return the saved record."""

        sanitized_parent_id = (parent_id or "").strip()
        sanitized_parent_type = (parent_type or "").strip().lower()
        sanitized_commentary = (commentary or "").strip()

        if not sanitized_parent_id:
            raise ValueError("parent_id is required")
        if sanitized_parent_type not in ("message", "annotation"):
            raise ValueError("parent_type must be 'message' or 'annotation'")
        if not sanitized_commentary:
            raise ValueError("commentary must not be empty")

        try:
            validate_newsletter_privacy(sanitized_commentary)
        except PrivacyViolationError as exc:  # pragma: no cover - defensive path
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
                raise ValueError(f"parent annotation with id {sanitized_parent_id} does not exist")

        row = self._connection.execute(
            f"""
            INSERT INTO {ANNOTATIONS_TABLE} (parent_id, parent_type, author, commentary, created_at)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
            """,
            [
                sanitized_parent_id,
                sanitized_parent_type,
                ANNOTATION_AUTHOR,
                sanitized_commentary,
                created_at,
            ],
        ).fetchone()
        if row is None:
            raise RuntimeError("Failed to insert annotation")
        annotation_id = int(row[0])

        return Annotation(
            id=annotation_id,
            parent_id=sanitized_parent_id,
            parent_type=sanitized_parent_type,
            author=ANNOTATION_AUTHOR,
            commentary=sanitized_commentary,
            created_at=created_at,
        )

    def list_annotations_for_message(self, msg_id: str) -> list[Annotation]:
        """Return annotations for ``msg_id`` ordered by creation time."""

        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return []

        records = self._fetch_records(
            f"""
            SELECT id, parent_id, parent_type, author, commentary, created_at
            FROM {ANNOTATIONS_TABLE}
            WHERE parent_id = ? AND parent_type = 'message'
            ORDER BY created_at ASC, id ASC
            """,
            [sanitized_msg_id],
        )

        return [self._row_to_annotation(row) for row in records]

    def get_last_annotation_id(self, msg_id: str) -> int | None:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""

        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return None

        cursor = self._connection.execute(
            f"""
            SELECT id FROM {ANNOTATIONS_TABLE}
            WHERE parent_id = ? AND parent_type = 'message'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [sanitized_msg_id],
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    def iter_all_annotations(self) -> Iterable[Annotation]:
        """Yield all annotations sorted by insertion order."""

        records = self._fetch_records(
            f"""
            SELECT id, parent_id, parent_type, author, commentary, created_at
            FROM {ANNOTATIONS_TABLE}
            ORDER BY created_at ASC, id ASC
            """
        )

        for row in records:
            yield self._row_to_annotation(row)

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
        # Get annotations as an Ibis table
        annotations_table = self._backend.table(ANNOTATIONS_TABLE)

        # Filter for annotations that are direct replies to messages
        message_annotations = annotations_table[annotations_table.parent_type == 'message']

        # Perform left join: messages with their annotations (if any)
        # This preserves all messages even if they don't have annotations
        joined = messages_table.left_join(
            message_annotations, messages_table.message_id == message_annotations.parent_id
        )

        return joined

    @staticmethod
    def _row_to_annotation(row: dict[str, Any]) -> Annotation:
        created_at_obj = row["created_at"]
        if hasattr(created_at_obj, "to_pydatetime"):
            created_at = created_at_obj.to_pydatetime()
        elif isinstance(created_at_obj, datetime):
            created_at = created_at_obj
        else:
            # Handle string with potential 'Z' suffix
            dt_str = str(created_at_obj).replace("Z", "+00:00")
            created_at = datetime.fromisoformat(dt_str)

        # Normalize timezone to UTC
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


__all__ = ["Annotation", "AnnotationStore", "ANNOTATION_AUTHOR", "ANNOTATIONS_TABLE"]
