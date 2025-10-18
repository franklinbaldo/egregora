"""Tests for the DuckDB-based lightweight RAG pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np

import pytest

from egregora.rag.duckdb_simple import DuckDBSimpleConfig, DuckDBSimpleRAG, split_documents


def _stub_embed(dimension: int):
    def _inner(texts: list[str], _task_type: str) -> np.ndarray:
        vectors = []
        for text in texts:
            vector = np.zeros(dimension, dtype=float)
            if "RAG" in text or "retrieval" in text.lower():
                vector[0] = 1.0
            elif "DuckDB" in text:
                vector[1] = 1.0
            else:
                vector[-1] = 1.0
            norm = np.linalg.norm(vector)
            if norm == 0:
                vector[-1] = 1.0
                norm = 1.0
            vectors.append(vector / norm)
        return np.vstack(vectors)

    return _inner


def _stub_generate(query: str, docs: list[str]) -> str:
    joined = " | ".join(docs)
    return f"Q: {query}\nDocs: {joined}".strip()


def test_split_documents_respects_chunking() -> None:
    long_text = " ".join(["Sentence one." for _ in range(40)])
    chunks = split_documents([long_text], chunk_size=120, overlap=20)
    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks[:-1])


@pytest.mark.parametrize("db_filename", ["rag.duckdb", ":memory:"])
def test_duckdb_rag_roundtrip(tmp_path: Path, db_filename: str) -> None:
    db_path = ":memory:" if db_filename == ":memory:" else str(tmp_path / db_filename)
    config = DuckDBSimpleConfig(
        db_path=db_path,
        embedding_dimension=4,
        chunk_size=60,
        chunk_overlap=10,
        top_k=2,
    )
    rag = DuckDBSimpleRAG(config=config, embed_fn=_stub_embed(4), generate_fn=_stub_generate)
    try:
        rag.ingest(
            [
                "DuckDB brings vector search to analytics.",
                "RAG systems combine retrieval and generation.",
            ]
        )
        results = rag.retrieve("Explain RAG", top_k=1)
        assert results and "RAG" in results[0]
        answer = rag.generate("Explain RAG", results)
        assert "Explain RAG" in answer
    finally:
        rag.close()
