"""Persistence layer for writer conversation annotations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import ibis

from .privacy import validate_newsletter_privacy

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

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = ibis.duckdb.connect(str(self.db_path))
        self._initialize()

    @property
    def _connection(self):
        """Return the underlying DuckDB connection."""

        return self._backend.con

    def _initialize(self) -> None:
        self._backend.raw_sql(
            f"""
            CREATE TABLE IF NOT EXISTS {ANNOTATIONS_TABLE} (
                id BIGINT PRIMARY KEY,
                msg_id TEXT NOT NULL,
                author TEXT NOT NULL,
                commentary TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                parent_annotation_id BIGINT
            )
            """
        )
        self._backend.raw_sql(
            f"""
            CREATE INDEX IF NOT EXISTS idx_annotations_msg_id_created
            ON {ANNOTATIONS_TABLE} (msg_id, created_at)
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
        msg_id: str,
        commentary: str,
        *,
        parent_annotation_id: int | None = None,
    ) -> Annotation:
        """Persist an annotation and return the saved record."""

        sanitized_msg_id = (msg_id or "").strip()
        sanitized_commentary = (commentary or "").strip()

        if not sanitized_msg_id:
            raise ValueError("msg_id is required")
        if not sanitized_commentary:
            raise ValueError("my_commentary must not be empty")

        validate_newsletter_privacy(sanitized_commentary)

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
                raise ValueError(
                    f"parent_annotation_id {parent_annotation_id} does not exist"
                )

        next_id_cursor = self._connection.execute(
            f"SELECT COALESCE(MAX(id), 0) + 1 FROM {ANNOTATIONS_TABLE}"
        )
        annotation_id = int(next_id_cursor.fetchone()[0])

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

    def list_annotations_for_message(self, msg_id: str) -> list[Annotation]:
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

    def get_last_annotation_id(self, msg_id: str) -> int | None:
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

    def iter_all_annotations(self) -> Iterable[Annotation]:
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
    def _row_to_annotation(row: dict[str, object]) -> Annotation:
        created_at_obj = row["created_at"]
        created_at: datetime
        if hasattr(created_at_obj, "to_pydatetime"):
            created_at = created_at_obj.to_pydatetime()
        elif isinstance(created_at_obj, datetime):
            created_at = created_at_obj
        else:
            raise TypeError("created_at column must be datetime-like")

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        parent_raw = row.get("parent_annotation_id")
        if parent_raw is None or parent_raw == "":
            parent_id: int | None = None
        else:
            try:
                parent_id = int(parent_raw)
            except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError("parent_annotation_id must be numeric") from exc

        return Annotation(
            id=int(row["id"]),
            msg_id=str(row["msg_id"]),
            author=str(row["author"]),
            commentary=str(row["commentary"]),
            created_at=created_at,
            parent_annotation_id=parent_id,
        )


__all__ = ["Annotation", "AnnotationStore", "ANNOTATION_AUTHOR", "ANNOTATIONS_TABLE"]
