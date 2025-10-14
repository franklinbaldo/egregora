"""Tests covering the FastMCP DuckDB RAG helpers."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from egregora.rag_context.duckdb_setup import initialise_vector_store
from egregora.rag_context.server import FastMCPRAGServer


def _write_sample_parquet(path: Path) -> Path:
    frame = pl.DataFrame(
        {
            "id": [1, 2],
            "message": ["Discussão sobre IA", "Debate sobre ciência"],
            "vector": [[1.0, 0.0], [0.0, 1.0]],
        }
    )
    frame.write_parquet(path)
    return path


def test_initialise_vector_store_without_vss(tmp_path: Path) -> None:
    parquet_path = _write_sample_parquet(tmp_path / "embeddings.parquet")

    index = initialise_vector_store(parquet_path, install_vss=False)

    assert index.table_name == "posts"
    assert index.vector_column == "vector"
    assert index.vss_enabled is False

    results = index.query_similar([1.0, 0.0], limit=1)
    assert results.height == 1
    assert results["message"][0] == "Discussão sobre IA"
    assert "similarity" in results.columns


def test_initialise_vector_store_missing_vector(tmp_path: Path) -> None:
    path = tmp_path / "missing_vector.parquet"
    pl.DataFrame({"id": [1], "message": ["Sem vetor"]}).write_parquet(path)

    with pytest.raises(ValueError):
        initialise_vector_store(path, install_vss=False)


class _StubEmbedder:
    """Embedder returning deterministic vectors for testing."""

    def embed_text(self, text: str | None) -> list[float]:
        if not text:
            return []
        if "IA" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]


def test_fastmcp_server_search_with_stub_embedder(tmp_path: Path) -> None:
    parquet_path = _write_sample_parquet(tmp_path / "embeddings.parquet")
    server = FastMCPRAGServer(
        parquet_path=parquet_path,
        install_vss=False,
        embedder=_StubEmbedder(),
        default_top_k=2,
    )

    frame = server.search("Resumo IA")
    assert frame.height == 2
    assert frame["similarity"][0] >= frame["similarity"][1]

    response = server._search_tool("Resumo IA", k=2)
    assert response.snippets[0] == "Discussão sobre IA"
    assert response.k == 2
    assert response.results[0]["message"] == "Discussão sobre IA"
    assert isinstance(response.results[0]["similarity"], float)
