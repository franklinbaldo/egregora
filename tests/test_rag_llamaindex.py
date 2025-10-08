"""Unit tests for the LlamaIndex-powered PostRAG implementation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from egregora.rag.config import RAGConfig
from egregora.rag.index import PostRAG


def _write_markdown(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(body.strip() + "\n", encoding="utf-8")


@pytest.fixture()
def rag(tmp_path: Path) -> PostRAG:
    posts_root = tmp_path / "posts"
    daily_dir = posts_root / "group" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    _write_markdown(
        daily_dir,
        "2024-01-01.md",
        """
        # Boletim 1

        Conversas sobre inteligência artificial e inovação.
        """,
    )
    _write_markdown(
        daily_dir,
        "2024-01-05.md",
        """
        # Boletim 2

        Discussão sobre machine learning aplicado a dados públicos.
        """,
    )
    _write_markdown(
        daily_dir,
        "2023-12-15.md",
        """
        # Boletim 3

        Conversas gerais sobre tecnologia, startups e IA responsável.
        """,
    )

    config = RAGConfig(
        persist_dir=tmp_path / "vector_store",
        cache_dir=tmp_path / "embedding_cache",
        chunk_size=256,
        chunk_overlap=32,
        min_similarity=0.0,
    )

    return PostRAG(posts_dir=posts_root, config=config)


def test_update_index_rebuilds_vector_store(rag: PostRAG) -> None:
    result = rag.update_index(force_rebuild=True)

    assert result["posts_count"] == 3
    assert result["chunks_count"] > 0

    stats = rag.get_stats()
    assert stats.total_posts == 3
    assert stats.total_chunks == result["chunks_count"]
    assert stats.persist_dir.exists()


def test_search_returns_relevant_chunks(rag: PostRAG) -> None:
    rag.update_index(force_rebuild=True)

    hits = rag.search("inteligência artificial", top_k=2, min_similarity=0.0)
    assert hits, "Expected at least one relevant chunk"

    first = hits[0]
    metadata = getattr(first.node, "metadata", {})
    assert metadata.get("file_name") in {"2024-01-01.md", "2023-12-15.md"}
    assert "inteligência" in first.node.get_content().lower()


def test_exclude_recent_days_filters_chunks(tmp_path: Path) -> None:
    posts_root = tmp_path / "letters"
    daily_dir = posts_root / "group" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    today = date.today()
    recent_day = today - timedelta(days=3)
    old_day = today - timedelta(days=60)

    _write_markdown(
        daily_dir,
        f"{recent_day.isoformat()}.md",
        "Discussão recente sobre agentes de IA",
    )
    _write_markdown(
        daily_dir,
        f"{old_day.isoformat()}.md",
        "Resumo antigo com notas sobre machine learning clássico",
    )

    config = RAGConfig(
        persist_dir=tmp_path / "vec_store",
        cache_dir=tmp_path / "cache",
        min_similarity=0.0,
    )

    rag = PostRAG(posts_dir=posts_root, config=config)
    rag.update_index(force_rebuild=True)

    hits = rag.search("machine learning", top_k=5, min_similarity=0.0, exclude_recent_days=30)
    assert hits, "Expected the older chunk to be returned"
    for hit in hits:
        metadata = getattr(hit.node, "metadata", {})
        assert metadata.get("date") == old_day.isoformat()


def test_export_embeddings_to_parquet(tmp_path: Path) -> None:
    posts_root = tmp_path / "letters"
    daily_dir = posts_root / "group" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    _write_markdown(
        daily_dir,
        "2024-02-01.md",
        "Discussão sobre coordenação e estratégia de IA",
    )
    _write_markdown(
        daily_dir,
        "2024-02-02.md",
        "Análise detalhada de dados compartilhados",
    )

    export_path = tmp_path / "artifacts" / "chunks.parquet"

    config = RAGConfig(
        persist_dir=tmp_path / "vec",
        cache_dir=tmp_path / "cache",
        export_embeddings=True,
        embedding_export_path=export_path,
        min_similarity=0.0,
    )

    rag = PostRAG(posts_dir=posts_root, config=config)
    stats = rag.update_index(force_rebuild=True)

    assert export_path.exists(), "Expected embeddings parquet to be created"

    df = pl.read_parquet(export_path)
    assert df.height == stats["chunks_count"]
    assert {
        "chunk_id",
        "doc_id",
        "file_name",
        "date",
        "text",
        "embedding_dimension",
        "embedding",
    } <= set(df.columns)

    first = df.row(0, named=True)
    assert isinstance(first["embedding"], list)
    assert len(first["embedding"]) == config.embedding_dimension
    assert first["embedding_dimension"] == config.embedding_dimension
