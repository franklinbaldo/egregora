"""Content-addressed document abstraction and storage protocols.

This module now aliases the core types from `egregora.core` to maintain backward compatibility
while transitioning to the V3 architecture.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from egregora.core.ports import OutputSink, UrlConvention
from egregora.core.types import Author, Category, Document, DocumentType, NAMESPACE_DOCUMENT

if TYPE_CHECKING:
    from ibis.expr.types import Table


@dataclass
class DocumentCollection:
    """Batch of documents produced by a single operation (e.g., one window)."""

    documents: list[Document]
    window_label: str | None = None

    def by_type(self, doc_type: DocumentType) -> list[Document]:
        return [doc for doc in self.documents if doc.type == doc_type]

    def find_children(self, parent_id: str) -> list[Document]:
        return [doc for doc in self.documents if doc.parent_id == parent_id]

    def find_by_id(self, document_id: str) -> Document | None:
        for doc in self.documents:
            if doc.document_id == document_id:
                return doc
        return None

    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[Document]:
        return iter(self.documents)


class MediaAsset(Document):
    r"""Specialized Document for binary media assets managed by the pipeline."""

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.type != DocumentType.MEDIA:
            msg = f"MediaAsset must have type MEDIA, got {self.type}"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class UrlContext:
    """Context information required when generating canonical URLs."""

    base_url: str = ""
    site_prefix: str = ""
    base_path: Path | None = None
    locale: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """Lightweight description of a document available in an output sink.

    Used for efficient document enumeration without loading full content.
    Returned by OutputSink.list() for memory-efficient iteration.
    """

    identifier: str
    doc_type: DocumentType | None
    metadata: dict[str, object]
