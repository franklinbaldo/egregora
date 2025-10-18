"""Configuration helpers for the DuckDB-based RAG pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from .duckdb_simple import DuckDBSimpleConfig


class RAGConfig(BaseModel):
    """High level configuration for :class:`DuckDBSimpleRAG`."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    enabled: bool = False
    db_path: str = ":memory:"
    embedding_model: str = DuckDBSimpleConfig.embedding_model
    generation_model: str = DuckDBSimpleConfig.generation_model
    embedding_dimension: int = DuckDBSimpleConfig.embedding_dimension
    chunk_size: int = DuckDBSimpleConfig.chunk_size
    chunk_overlap: int = DuckDBSimpleConfig.chunk_overlap
    top_k: int = DuckDBSimpleConfig.top_k

    @field_validator("embedding_dimension", "chunk_size", "top_k", mode="before")
    @classmethod
    def _validate_positive_int(cls, value: Any, info: ValidationInfo) -> int:
        try:
            ivalue = int(value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - validation detail
            raise TypeError(f"{info.field_name} must be an integer") from exc
        if ivalue < 1:
            raise ValueError(f"{info.field_name} must be a positive integer")
        return ivalue

    @field_validator("chunk_overlap", mode="before")
    @classmethod
    def _validate_overlap(cls, value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            ivalue = int(value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - validation detail
            raise TypeError("chunk_overlap must be an integer") from exc
        if ivalue < 0:
            raise ValueError("chunk_overlap must be zero or a positive integer")
        return ivalue

    @field_validator("db_path", mode="before")
    @classmethod
    def _coerce_db_path(cls, value: Any) -> str:
        if value in (None, ""):
            return ":memory:"
        return str(value)

    def to_duckdb_config(self) -> DuckDBSimpleConfig:
        """Build a :class:`DuckDBSimpleConfig` from this model."""

        return DuckDBSimpleConfig(
            embedding_model=self.embedding_model,
            generation_model=self.generation_model,
            embedding_dimension=self.embedding_dimension,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            top_k=self.top_k,
            db_path=self.db_path,
        )


__all__ = ["RAGConfig"]
