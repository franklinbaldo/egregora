"""Conversation annotation system for threading, metadata, and conversation units.

This module provides a unified annotation storage layer that treats annotations
as standard Document objects, persisting them via ContentRepository.

Architecture:
    - Annotations are DocumentType.ANNOTATION Documents
    - Stored in the 'annotations' table
    - UUID-based deterministic identity (v5)
    - Parent-child relationships via parent_id/parent_type metadata
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from egregora.data_primitives.document import Document, DocumentType
from egregora.database import schemas as database_schema

if TYPE_CHECKING:
    from collections.abc import Iterable

    from egregora.database.repository import ContentRepository

logger = logging.getLogger(__name__)

# Default author identifier for all annotations created by the writer agent
ANNOTATION_AUTHOR = "egregora"

# DuckDB table name where annotations are persisted
ANNOTATIONS_TABLE = "annotations"


class AnnotationStore:
    """High-level API for managing conversation annotations as Documents.

    Refactored in V2 to use ContentRepository for persistence, eliminating
    redundant storage logic and sequence dependency.
    """

    def __init__(
        self,
        repository: ContentRepository,
    ) -> None:
        """Initialize annotation store.

        Args:
            repository: Unified content repository for document persistence

        """
        self.repository = repository
        self._initialize()

    def _initialize(self) -> None:
        """Ensure annotations table exists."""
        database_schema.create_table_if_not_exists(
            self.repository.db.ibis_conn,
            ANNOTATIONS_TABLE,
            database_schema.ANNOTATIONS_SCHEMA,
        )

    def save_annotation(
        self,
        parent_id: str,
        parent_type: Literal["message", "annotation"],
        commentary: str,
        author_id: str = ANNOTATION_AUTHOR,
        category: str | None = "Annotations",
        tags: list[str] | None = None,
    ) -> Document:
        """Persist an annotation Document and return it.

        Uses UUID v5 for deterministic identity based on parent and content.
        """
        created_at = datetime.now(UTC)

        # Deterministic UUID based on parent and commentary to prevent duplicates
        namespace = uuid.NAMESPACE_URL
        seed = f"annotation:{parent_id}:{commentary}"
        annotation_id = str(uuid.uuid5(namespace, seed))

        metadata = {
            "parent_id": parent_id,
            "parent_type": parent_type,
            "author_id": author_id,
            "category": category,
            "tags": tags or [],
            "slug": f"annotation-{annotation_id[:8]}",
            "title": f"Annotation on {parent_id}",
        }

        doc = Document(
            id=annotation_id,
            content=commentary,
            type=DocumentType.ANNOTATION,
            metadata=metadata,
            created_at=created_at,
        )

        self.repository.save(doc)
        return doc

    def list_annotations_for_message(self, msg_id: str) -> list[Document]:
        """Return annotation Documents for ``msg_id`` ordered by creation time."""
        try:
            t = self.repository.db.read_table(ANNOTATIONS_TABLE)
            res = (
                t.filter((t.parent_id == msg_id) & (t.parent_type == "message"))
                .order_by(t.created_at)
                .execute()
            )
            if res.empty:
                return []

            records = res.to_dict(orient="records")
            return [self.repository._row_to_document(row, DocumentType.ANNOTATION) for row in records]
        except Exception as e:
            logger.debug("Failed to list annotations for message %s: %s", msg_id, e)
            return []

    def iter_all_annotations(self) -> Iterable[Document]:
        """Yield all annotation Documents sorted by insertion order."""
        try:
            t = self.repository.db.read_table(ANNOTATIONS_TABLE)
            res = t.order_by(t.created_at).execute()
            records = res.to_dict(orient="records")
            for row in records:
                yield self.repository._row_to_document(row, DocumentType.ANNOTATION)
        except Exception as e:
            logger.debug("Failed to iterate annotations: %s", e)

    def join_with_messages(self, messages_table: Any) -> Any:
        """Join annotations with messages using message_id as foreign key."""
        annotations_table = self.repository.db.ibis_conn.table(ANNOTATIONS_TABLE)
        message_annotations = annotations_table[annotations_table.parent_type == "message"]

        # Rename columns to avoid conflicts if necessary
        # But usually we just want to join them
        return messages_table.left_join(
            message_annotations, messages_table.msg_id == message_annotations.parent_id
        )


__all__ = ["ANNOTATIONS_TABLE", "ANNOTATION_AUTHOR", "AnnotationStore"]
