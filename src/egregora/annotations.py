"""Persistence layer for writer conversation annotations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import sqlite3

from .privacy import PrivacyViolationError, validate_newsletter_privacy

ANNOTATION_AUTHOR = "egregora"


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
    """SQLite-backed storage for writer annotations."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS annotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT NOT NULL,
                    author TEXT NOT NULL,
                    commentary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    parent_annotation_id INTEGER,
                    FOREIGN KEY(parent_annotation_id) REFERENCES annotations(id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_annotations_msg_id_created
                ON annotations (msg_id, created_at)
                """
            )

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

        try:
            validate_newsletter_privacy(sanitized_commentary)
        except PrivacyViolationError as exc:  # pragma: no cover - defensive path
            raise ValueError(str(exc)) from exc

        created_at = datetime.now(timezone.utc)

        with self._connect() as conn:
            if parent_annotation_id is not None:
                exists = conn.execute(
                    "SELECT 1 FROM annotations WHERE id = ?",
                    (parent_annotation_id,),
                ).fetchone()
                if not exists:
                    raise ValueError(
                        f"parent_annotation_id {parent_annotation_id} does not exist"
                    )
            cursor = conn.execute(
                """
                INSERT INTO annotations (msg_id, author, commentary, created_at, parent_annotation_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    sanitized_msg_id,
                    ANNOTATION_AUTHOR,
                    sanitized_commentary,
                    created_at.isoformat(),
                    parent_annotation_id,
                ),
            )
            annotation_id = cursor.lastrowid

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

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, msg_id, author, commentary, created_at, parent_annotation_id
                FROM annotations
                WHERE msg_id = ?
                ORDER BY datetime(created_at) ASC, id ASC
                """,
                (sanitized_msg_id,),
            ).fetchall()

        annotations: list[Annotation] = []
        for row in rows:
            created_at_raw = row["created_at"]
            created_at = (
                datetime.fromisoformat(created_at_raw)
                if isinstance(created_at_raw, str)
                else created_at_raw
            )
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            annotations.append(
                Annotation(
                    id=row["id"],
                    msg_id=row["msg_id"],
                    author=row["author"],
                    commentary=row["commentary"],
                    created_at=created_at,
                    parent_annotation_id=row["parent_annotation_id"],
                )
            )

        return annotations

    def get_last_annotation_id(self, msg_id: str) -> int | None:
        """Return the most recent annotation ID for ``msg_id`` if any exist."""

        sanitized_msg_id = (msg_id or "").strip()
        if not sanitized_msg_id:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM annotations
                WHERE msg_id = ?
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 1
                """,
                (sanitized_msg_id,),
            ).fetchone()

        return row["id"] if row else None

    def iter_all_annotations(self) -> Iterable[Annotation]:
        """Yield all annotations sorted by insertion order."""

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, msg_id, author, commentary, created_at, parent_annotation_id
                FROM annotations
                ORDER BY datetime(created_at) ASC, id ASC
                """
            ).fetchall()

        for row in rows:
            created_at_raw = row["created_at"]
            created_at = (
                datetime.fromisoformat(created_at_raw)
                if isinstance(created_at_raw, str)
                else created_at_raw
            )
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            yield Annotation(
                id=row["id"],
                msg_id=row["msg_id"],
                author=row["author"],
                commentary=row["commentary"],
                created_at=created_at,
                parent_annotation_id=row["parent_annotation_id"],
            )


__all__ = ["Annotation", "AnnotationStore", "ANNOTATION_AUTHOR"]
