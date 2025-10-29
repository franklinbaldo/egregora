"""Typed option containers shared by RAG helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal


@dataclass(slots=True)
class SearchOptions:
    """Parameters controlling vector store search behaviour."""

    top_k: int = 5
    min_similarity: float = 0.7
    tag_filter: list[str] | None = None
    date_after: date | datetime | str | None = None
    document_type: Literal["post", "media", None] = None
    media_types: list[str] | None = None
    mode: Literal["ann", "exact"] = "ann"
    nprobe: int | None = None
    overfetch: int | None = None


@dataclass(slots=True)
class MediaQueryOptions:
    """Friendly wrapper for media retrieval parameters."""

    top_k: int = 5
    min_similarity: float = 0.7
    media_types: list[str] | None = None
    deduplicate: bool = True
    mode: Literal["ann", "exact"] = "ann"
    nprobe: int | None = None
    overfetch: int | None = None
