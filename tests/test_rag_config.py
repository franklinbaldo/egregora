"""Tests for the simplified DuckDB-backed RAG configuration."""

from __future__ import annotations

import pytest

from egregora.rag.config import RAGConfig
from egregora.rag.duckdb_simple import DuckDBSimpleConfig


def test_rag_config_defaults_map_to_duckdb_config() -> None:
    config = RAGConfig()
    duckdb_config = config.to_duckdb_config()
    assert isinstance(duckdb_config, DuckDBSimpleConfig)
    assert duckdb_config.chunk_size == config.chunk_size
    assert duckdb_config.chunk_overlap == config.chunk_overlap
    assert duckdb_config.embedding_dimension == config.embedding_dimension
    assert duckdb_config.top_k == config.top_k


def test_rag_config_accepts_string_inputs() -> None:
    config = RAGConfig(
        enabled=True,
        db_path="rag.db",
        chunk_size="128",
        chunk_overlap="16",
        top_k="5",
        embedding_dimension="256",
    )
    duckdb_config = config.to_duckdb_config()
    assert duckdb_config.db_path == "rag.db"
    assert duckdb_config.chunk_size == 128
    assert duckdb_config.chunk_overlap == 16
    assert duckdb_config.top_k == 5
    assert duckdb_config.embedding_dimension == 256


def test_rag_config_rejects_invalid_numbers() -> None:
    with pytest.raises(ValueError):
        RAGConfig(chunk_size=0)
    with pytest.raises(ValueError):
        RAGConfig(top_k=0)
    with pytest.raises(ValueError):
        RAGConfig(chunk_overlap=-1)
