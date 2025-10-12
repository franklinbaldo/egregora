"""Configuration options for the LlamaIndex-based RAG stack."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

class RAGConfig(BaseModel):
    """Simplified RAG configuration with smart defaults."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = True

    # Retrieval (most important settings)
    top_k: int = 3
    min_similarity: float = 0.70
    exclude_recent_days: int = 7

    # Query generation (simplified)
    max_keywords: int = 5
    max_context_chars: int = 800

    # Chunking (good defaults, keep)
    chunk_size: int = 1800
    chunk_overlap: int = 360

    # Embeddings (simplified)
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768
    enable_cache: bool = True
    cache_dir: Path = Field(default_factory=lambda: Path("cache/rag"))

    # Storage (simplified)
    vector_store_type: str = "chroma"
    persist_dir: Path = Field(default_factory=lambda: Path("cache/rag/chroma"))
    collection_name: str = "posts"

    @field_validator("top_k", "max_keywords")
    @classmethod
    def _validate_positive_int(cls, value: Any, info: ValidationInfo) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError(f"{info.field_name} must be greater than zero")
        return ivalue

    @field_validator("exclude_recent_days")
    @classmethod
    def _validate_non_negative(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError("exclude_recent_days must be zero or a positive integer")
        return ivalue

    @field_validator("max_context_chars")
    @classmethod
    def _validate_context_chars(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("max_context_chars must be greater than zero")
        return ivalue

    @field_validator("min_similarity")
    @classmethod
    def _validate_similarity(cls, value: Any) -> float:
        fvalue = float(value)
        if not 0 <= fvalue <= 1:
            raise ValueError("min_similarity must be between 0 and 1")
        return fvalue

    @field_validator("chunk_size")
    @classmethod
    def _validate_chunk_size(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("chunk_size must be greater than zero")
        return ivalue

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, value: Any, _info: ValidationInfo) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError("chunk_overlap must be zero or positive")
        return ivalue

    @field_validator("embedding_dimension")
    @classmethod
    def _validate_embedding_dimension(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("embedding_dimension must be greater than zero")
        return ivalue

    @field_validator("cache_dir", "persist_dir")
    @classmethod
    def _ensure_path(cls, value: Any) -> Path:
        return Path(value)

    @model_validator(mode="after")
    def _validate_overlap_bounds(self) -> RAGConfig:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


__all__ = ["RAGConfig"]
