"""Configuration options for the LlamaIndex-based RAG stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

_DEPRECATED_RAG_KEYS = {"use_gemini_embeddings"}


def sanitize_rag_config_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``payload`` without deprecated configuration keys."""

    return {
        key: value
        for key, value in payload.items()
        if key not in _DEPRECATED_RAG_KEYS
    }


def _default_mcp_args() -> tuple[str, ...]:
    return (
        "run",
        "python",
        "-m",
        "egregora.mcp_server.server",
    )


class RAGConfig(BaseModel):
    """Configuration for post retrieval powered by LlamaIndex."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False

    # Retrieval behaviour
    top_k: int = 5
    min_similarity: float = 0.65
    exclude_recent_days: int = 7

    # Query generation helpers
    max_context_chars: int = 1200
    max_keywords: int = 8
    classifier_max_llm_calls: int | None = 200
    classifier_token_budget: int | None = 20000

    # MCP integration
    use_mcp: bool = True
    mcp_command: str = "uv"
    mcp_args: tuple[str, ...] = Field(default_factory=_default_mcp_args)

    # Chunking parameters (tokens)
    chunk_size: int = 1800
    chunk_overlap: int = 360

    # Embeddings
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 768
    enable_cache: bool = True
    cache_dir: Path = Field(default_factory=lambda: Path("cache/embeddings"))
    export_embeddings: bool = False
    embedding_export_path: Path = Field(
        default_factory=lambda: Path("artifacts/embeddings/post_chunks.parquet"))

    # Vector store
    vector_store_type: str = "simple"
    persist_dir: Path = Field(default_factory=lambda: Path("cache/vector_store"))
    collection_name: str = "posts"

    @field_validator("top_k", "max_keywords")
    @classmethod
    def _validate_positive_int(
        cls, value: Any, info: ValidationInfo
    ) -> int:
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
    def _validate_overlap(
        cls, value: Any, _info: ValidationInfo
    ) -> int:
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

    @field_validator("cache_dir", "embedding_export_path", "persist_dir")
    @classmethod
    def _ensure_path(cls, value: Any) -> Path:
        return Path(value)

    @field_validator("mcp_args")
    @classmethod
    def _coerce_mcp_args(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(str(item) for item in value)

    @model_validator(mode="after")
    def _validate_overlap_bounds(self) -> "RAGConfig":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        return self


__all__ = ["RAGConfig", "sanitize_rag_config_payload"]
