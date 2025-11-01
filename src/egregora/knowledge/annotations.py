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
        # Create table using consolidated schema
        database_schema.create_table_if_not_exists(
            self._backend,
            ANNOTATIONS_TABLE,
            database_schema.ANNOTATIONS_SCHEMA,
        )
        self._migrate_annotations_table_if_needed()
        # Add primary key using raw connection
        database_schema.add_primary_key(self._connection, ANNOTATIONS_TABLE, "id")
        self._backend.raw_sql(
            f"""
            CREATE INDEX IF NOT EXISTS idx_annotations_parent_created
            ON {ANNOTATIONS_TABLE} (parent_id, parent_type, created_at)
            """
        )

    def _migrate_annotations_table_if_needed(self) -> None:
        """Upgrade legacy annotation tables to the unified parent schema."""

        if ANNOTATIONS_TABLE not in self._backend.list_tables():
            return

        cursor = self._connection.execute(f"PRAGMA table_info('{ANNOTATIONS_TABLE}')")
        existing_columns = {row[1] for row in cursor.fetchall()}

        has_parent_id = "parent_id" in existing_columns
        has_parent_type = "parent_type" in existing_columns

        if has_parent_id and has_parent_type:
            return

        has_msg_id = "msg_id" in existing_columns
        has_parent_annotation_id = "parent_annotation_id" in existing_columns

        # Ensure the new columns exist before attempting to backfill data.
        if not has_parent_id:
            self._connection.execute(
                f"ALTER TABLE {ANNOTATIONS_TABLE} ADD COLUMN parent_id VARCHAR"
            )
        if not has_parent_type:
            self._connection.execute(
                f"ALTER TABLE {ANNOTATIONS_TABLE} ADD COLUMN parent_type VARCHAR"
            )

        annotation_condition = "FALSE"
        annotation_value = "NULL"
        if has_parent_annotation_id:
            annotation_condition = (
                "(parent_annotation_id IS NOT NULL AND "
                "CAST(parent_annotation_id AS VARCHAR) <> '')"
            )
            annotation_value = "CAST(parent_annotation_id AS VARCHAR)"

        message_condition = "FALSE"
        message_value = "NULL"
        if has_msg_id:
            message_condition = "(msg_id IS NOT NULL AND CAST(msg_id AS VARCHAR) <> '')"
            message_value = "CAST(msg_id AS VARCHAR)"

        self._connection.execute(
            f"""
            UPDATE {ANNOTATIONS_TABLE}
            SET parent_id = CASE
                    WHEN {annotation_condition} THEN {annotation_value}
                    WHEN {message_condition} THEN {message_value}
                    ELSE parent_id
                END,
                parent_type = CASE
                    WHEN {annotation_condition} THEN 'annotation'
                    WHEN {message_condition} THEN 'message'
                    ELSE parent_type
                END
            WHERE parent_id IS NULL OR parent_id = ''
               OR parent_type IS NULL OR parent_type = ''
            """
        )

        remaining = self._connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {ANNOTATIONS_TABLE}
            WHERE parent_id IS NULL OR parent_id = ''
               OR parent_type IS NULL OR parent_type = ''
            """
        ).fetchone()
        if remaining and int(remaining[0]) > 0:
            raise RuntimeError(
                "Failed to migrate annotations table to parent_id/parent_type schema"
            )

        if has_parent_annotation_id:
            self._connection.execute(
                f"ALTER TABLE {ANNOTATIONS_TABLE} DROP COLUMN parent_annotation_id"
            )
        if has_msg_id:
            self._connection.execute("DROP INDEX IF EXISTS idx_annotations_msg_id_created")
            self._connection.execute(f"ALTER TABLE {ANNOTATIONS_TABLE} DROP COLUMN msg_id")

        invalidate_metadata = getattr(self._backend, "invalidate_metadata", None)
        if callable(invalidate_metadata):
            invalidate_metadata(ANNOTATIONS_TABLE)

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

        next_id_cursor = self._connection.execute(
            f"SELECT COALESCE(MAX(id), 0) + 1 FROM {ANNOTATIONS_TABLE}"
        )
        row = next_id_cursor.fetchone()
        if row is None:
            raise RuntimeError("Could not get next annotation ID")
        annotation_id = int(row[0])

        self._connection.execute(
            f"""
            INSERT INTO {ANNOTATIONS_TABLE} (id, parent_id, parent_type, author, commentary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                annotation_id,
                sanitized_parent_id,
                sanitized_parent_type,
                ANNOTATION_AUTHOR,
                sanitized_commentary,
                created_at,
            ],
        )

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
