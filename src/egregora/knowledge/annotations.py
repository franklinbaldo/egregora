"""Persistence layer for writer conversation annotations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

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
    msg_id: str
    author: str
    commentary: str
    created_at: datetime
    parent_annotation_id: int | None


class AnnotationStore:
    """DuckDB-backed storage for writer annotations accessed via Ibis."""

    def __init__(self, db_path: Annotated[Path, "The file path for the DuckDB database"]) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = ibis.duckdb.connect(str(self.db_path))
        self._initialize()

    @property
    def _connection(
        self,
    ) -> Annotated[duckdb.DuckDBPyConnection, "The active DuckDB database connection"]:
        """Return the underlying DuckDB connection."""

        return self._backend.con

    def _initialize(self) -> None:
        # Create table using consolidated schema
        database_schema.create_table_if_not_exists(
            self._backend,
            ANNOTATIONS_TABLE,
            database_schema.ANNOTATIONS_SCHEMA,
        )
        # Add primary key using raw connection
        database_schema.add_primary_key(self._connection, ANNOTATIONS_TABLE, "id")
        self._backend.raw_sql(
            f"""
            CREATE INDEX IF NOT EXISTS idx_annotations_msg_id_created
            ON {ANNOTATIONS_TABLE} (msg_id, created_at)
            """
        )

    def _fetch_records(
        self,
        query: Annotated[str, "The SQL query to execute"],
        params: Annotated[
            Sequence[object] | None, "Optional sequence of parameters for the SQL query"
        ] = None,
    ) -> Annotated[list[dict[str, object]], "A list of dictionaries representing the fetched rows"]:
        cursor = self._connection.execute(query, params or [])
        column_names = [description[0] for description in cursor.description]
        return [dict(zip(column_names, row, strict=False)) for row in cursor.fetchall()]

    def save_annotation(
        self,
        msg_id: Annotated[str, "The identifier of the message being annotated"],
        commentary: Annotated[str, "The commentary text for the annotation"],
        *,
        parent_annotation_id: Annotated[int | None, "Optional ID of a parent annotation"] = None,
    ) -> Annotated[Annotation, "The newly created and saved annotation object"]:
        """Persist an annotation and return the saved record."""

        sanitized_msg_id = (msg_id or "").strip()
        sanitized_commentary = (commentary or "").strip()

        if not sanitized_msg_id:
            raise ValueError("msg_id is required")
        if not sanitized_commentary:
            raise ValueError("my_commentary must not be empty")

        try:
            validate_newsletter_privacy(sanitized_commentary)
        except PrivacyViolationError as exc:  # pragma: no cover - defensive path
            raise ValueError(str(exc)) from exc

        created_at = datetime.now(UTC)

        annotations_table = self._backend.table(ANNOTATIONS_TABLE)

        if parent_annotation_id is not None:
            parent_exists = int(
                annotations_table.filter(annotations_table.id == parent_annotation_id)
                .limit(1)
                .count()
                .execute()
            )
            if parent_exists == 0:
                raise ValueError(f"parent_annotation_id {parent_annotation_id} does not exist")

        next_id_cursor = self._connection.execute(
            f"SELECT COALESCE(MAX(id), 0) + 1 FROM {ANNOTATIONS_TABLE}"
        )
        row = next_id_cursor.fetchone()
        if row is None:
            raise RuntimeError("Could not get next annotation ID")
        annotation_id = int(row[0])

        self._connection.execute(
            f"""
            INSERT INTO {ANNOTATIONS_TABLE} (id, msg_id, author, commentary, created_at, parent_annotation_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                annotation_id,
                sanitized_msg_id,
                ANNOTATION_AUTHOR,
                sanitized_commentary,
                created_at,
                parent_annotation_id,
            ],
        )

        return Annotation(
            id=annotation_id,
            msg_id=sanitized_msg_id,
            author=ANNOTATION_AUTHOR,
            commentary=sanitized_commentary,
            created_at=created_at,
            parent_annotation_id=parent_annotation_id,
        )

    def list_annotations_for_message(
        self, msg_id: Annotated[str, "The message ID to retrieve annotations for"]
    ) -> Annotated[list[Annotation], "A list of annotations for the given message"]:
        """Return annotations for ``msg_id`` ordered by creation time."""

        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return []

        records = self._fetch_records(
            f"""
            SELECT id, msg_id, author, commentary, created_at, parent_annotation_id
            FROM {ANNOTATIONS_TABLE}
            WHERE msg_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            [sanitized_msg_id],
        )

        return [self._row_to_annotation(row) for row in records]

    def get_last_annotation_id(
        self, msg_id: Annotated[str, "The message ID to find the last annotation for"]
    ) -> Annotated[int | None, "The ID of the most recent annotation, or None"]:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""

        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return None

        cursor = self._connection.execute(
            f"""
            SELECT id FROM {ANNOTATIONS_TABLE}
            WHERE msg_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            [sanitized_msg_id],
        )
        row = cursor.fetchone()
        return int(row[0]) if row else None

    def iter_all_annotations(
        self,
    ) -> Annotated[Iterable[Annotation], "An iterator over all stored annotations"]:
        """Yield all annotations sorted by insertion order."""

        records = self._fetch_records(
            f"""
            SELECT id, msg_id, author, commentary, created_at, parent_annotation_id
            FROM {ANNOTATIONS_TABLE}
            ORDER BY created_at ASC, id ASC
            """
        )

        for row in records:
            yield self._row_to_annotation(row)

    @staticmethod
    def _row_to_annotation(
        row: Annotated[dict[str, Any], "A dictionary representing a row from the database"],
    ) -> Annotated[Annotation, "An Annotation data object"]:
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

        parent_raw = row.get("parent_annotation_id")
        parent_id = int(parent_raw) if parent_raw is not None else None

        return Annotation(
            id=int(row["id"]),
            msg_id=str(row["msg_id"]),
            author=str(row["author"]),
            commentary=str(row["commentary"]),
            created_at=created_at,
            parent_annotation_id=parent_id,
        )


__all__ = ["Annotation", "AnnotationStore", "ANNOTATION_AUTHOR", "ANNOTATIONS_TABLE"]
