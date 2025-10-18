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


def _default_keyword_stop_words() -> tuple[str, ...]:
    return (
        "about",
        "and",
        "are",
        "but",
        "com",
        "for",
        "from",
        "http",
        "https",
        "not",
        "that",
        "the",
        "this",
        "was",
        "were",
        "with",
        "you",
    )


class RetrievalSettings(BaseModel):
    """Similarity search parameters."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    top_k: int = 5
    min_similarity: float = 0.65
    exclude_recent_days: int = 7

    @field_validator("top_k")
    @classmethod
    def _validate_top_k(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("top_k must be greater than zero")
        return ivalue

    @field_validator("min_similarity")
    @classmethod
    def _validate_similarity(cls, value: Any) -> float:
        fvalue = float(value)
        if not 0 <= fvalue <= 1:
            raise ValueError("min_similarity must be between 0 and 1")
        return fvalue

    @field_validator("exclude_recent_days")
    @classmethod
    def _validate_exclude_days(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError("exclude_recent_days must be zero or a positive integer")
        return ivalue


class QuerySettings(BaseModel):
    """LLM-assisted query generation settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    max_context_chars: int = 1200
    max_keywords: int = 8
    keyword_stop_words: tuple[str, ...] | None = Field(default_factory=_default_keyword_stop_words)
    classifier_max_llm_calls: int | None = 200
    classifier_token_budget: int | None = 20000

    @field_validator("max_context_chars")
    @classmethod
    def _validate_context_chars(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("max_context_chars must be greater than zero")
        return ivalue

    @field_validator("max_keywords")
    @classmethod
    def _validate_max_keywords(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("max_keywords must be greater than zero")
        return ivalue

    @field_validator("keyword_stop_words", mode="before")
    @classmethod
    def _coerce_stop_words(cls, value: Any) -> tuple[str, ...] | None:
        if value in (None, "", []):
            return None
        if isinstance(value, str):
            items = [part.strip().lower() for part in value.split(",") if part.strip()]
            return tuple(items) or None
        if isinstance(value, Sequence):
            cleaned = [str(item).strip().lower() for item in value if str(item).strip()]
            return tuple(cleaned) or None
        return None

    @field_validator("classifier_max_llm_calls", "classifier_token_budget")
    @classmethod
    def _validate_classifier_limits(cls, value: Any) -> int | None:
        if value in (None, ""):
            return None
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("classifier limits must be positive integers")
        return ivalue


class ChunkingSettings(BaseModel):
    """Chunk sizes used when indexing Markdown posts."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    chunk_size: int = 1800
    chunk_overlap: int = 360

    @field_validator("chunk_size")
    @classmethod
    def _validate_chunk_size(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("chunk_size must be greater than zero")
        return ivalue

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_chunk_overlap(cls, value: Any, _info: ValidationInfo) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError("chunk_overlap must be zero or positive")
        return ivalue


class EmbeddingSettings(BaseModel):
    """Embedding model and cache configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 768
    enable_cache: bool = True
    cache_dir: Path = Field(default_factory=lambda: Path("cache/embeddings"))
    export_embeddings: bool = False
    embedding_export_path: Path = Field(
        default_factory=lambda: Path("artifacts/embeddings/post_chunks.parquet")
    )

    @field_validator("embedding_dimension")
    @classmethod
    def _validate_embedding_dimension(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("embedding_dimension must be greater than zero")
        return ivalue

    @field_validator("cache_dir", "embedding_export_path", mode="before")
    @classmethod
    def _ensure_path(cls, value: Any) -> Path:
        return Path(value)


class VectorStoreSettings(BaseModel):
    """Persistent vector store settings."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    vector_store_type: str = "simple"
    persist_dir: Path = Field(default_factory=lambda: Path("cache/vector_store"))
    collection_name: str = "posts"

    @field_validator("persist_dir", mode="before")
    @classmethod
    def _ensure_persist_dir(cls, value: Any) -> Path:
        return Path(value)


class MessageContextSettings(BaseModel):
    """Controls context windows when indexing chat messages."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    message_context_radius_before: int = 1
    message_context_radius_after: int = 1
    max_cached_days: int = 32

    @field_validator("message_context_radius_before", "message_context_radius_after")
    @classmethod
    def _validate_radius(cls, value: Any, info: ValidationInfo) -> int:
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError(f"{info.field_name} must be zero or positive")
        return ivalue

    @field_validator("max_cached_days")
    @classmethod
    def _validate_cached_days(cls, value: Any) -> int:
        ivalue = int(value)
        if ivalue < 1:
            raise ValueError("max_cached_days must be greater than zero")
        return ivalue


class RAGConfig(BaseModel):
    """Configuration for post retrieval powered by LlamaIndex."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    query: QuerySettings = Field(default_factory=QuerySettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    messages: MessageContextSettings = Field(default_factory=MessageContextSettings)

    _NAMESPACES = ("retrieval", "query", "chunking", "embedding", "vector_store", "messages")

    @model_validator(mode="after")
    def _validate_chunking_bounds(self) -> RAGConfig:
        if self.chunking.chunk_overlap >= self.chunking.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self

    def __getattr__(self, item: str) -> Any:
        for namespace_name in self._NAMESPACES:
            namespace = super().__getattribute__(namespace_name)
            if hasattr(namespace, item):
                return getattr(namespace, item)
        raise AttributeError(item)

    def __setattr__(self, name: str, value: Any) -> None:
        core_fields = {"enabled", *self._NAMESPACES}
        if name in core_fields or name.startswith("__"):
            super().__setattr__(name, value)
            return
        for namespace_name in self._NAMESPACES:
            try:
                namespace = super().__getattribute__(namespace_name)
            except AttributeError:
                break
            if hasattr(namespace, name):
                setattr(namespace, name, value)
                return
        super().__setattr__(name, value)


__all__ = [
    "RAGConfig",
    "RetrievalSettings",
    "QuerySettings",
    "ChunkingSettings",
    "EmbeddingSettings",
    "VectorStoreSettings",
    "MessageContextSettings",
]
