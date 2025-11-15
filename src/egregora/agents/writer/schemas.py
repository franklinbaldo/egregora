"""Pydantic schemas for the writer agent's tools and state."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from pathlib import Path


class PostMetadata(BaseModel):
    """Metadata schema for the write_post tool."""

    title: str
    slug: str
    date: str
    tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    authors: list[str] = Field(default_factory=list)
    category: str | None = None


class WritePostResult(BaseModel):
    status: str
    path: str


class WriteProfileResult(BaseModel):
    status: str
    path: str


class ReadProfileResult(BaseModel):
    content: str


class MediaItem(BaseModel):
    media_type: str | None = None
    media_path: str | None = None
    original_filename: str | None = None
    description: str | None = None
    similarity: float | None = None


class SearchMediaResult(BaseModel):
    results: list[MediaItem]


class AnnotationResult(BaseModel):
    status: str
    annotation_id: str | None = None
    parent_id: str | None = None
    parent_type: str | None = None


class BannerResult(BaseModel):
    status: str
    path: str | None = None


class WriterAgentReturn(BaseModel):
    """Final assistant response when the agent finishes."""

    summary: str | None = None
    notes: str | None = None


class WriterAgentState(BaseModel):
    """Immutable dependencies passed to agent tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)
    window_id: str
    url_convention: Any
    url_context: Any
    output_format: Any
    rag_store: Any
    annotations_store: Any | None
    batch_client: Any
    embedding_model: str
    retrieval_mode: str
    retrieval_nprobe: int | None
    retrieval_overfetch: int | None
