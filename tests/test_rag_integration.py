"""High-level integration tests for the embeddings-based RAG pipeline."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from egregora.config import PipelineConfig, RAGConfig
from egregora.rag.index import PostRAG
from egregora.rag.query_gen import QueryGenerator, QueryResult
from test_framework.helpers import create_test_zip


def _create_post(posts_root: Path, *, stem: str, body: str) -> Path:
    daily_dir = posts_root / "team" / "posts" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    path = daily_dir / f"{stem}.md"
    path.write_text(body, encoding="utf-8")
    return path


_STOPWORDS = {
    "de",
    "do",
    "da",
    "das",
    "dos",
    "e",
    "vamos",
    "sobre",
    "legal",
    "esse",
    "essa",
    "grupo",
    "teste",
    "franklin",
    "discutir",
}


def _stub_keyword_provider(text: str, *, max_keywords: int) -> list[str]:
    """Return deterministic keywords for tests without external providers."""

    keywords: list[str] = []
    for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", text.lower()):
        if token in _STOPWORDS or len(token) < 2:
            continue
        if token in keywords:
            continue
        keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def test_query_generation_whatsapp_content() -> None:
    """Query generation should extract meaningful terms from transcripts."""

    whatsapp_content = """03/10/2025 09:45 - Franklin: Teste de grupo sobre tecnologia
03/10/2025 09:46 - Franklin: Vamos discutir IA e machine learning
03/10/2025 09:47 - Franklin: Legal esse vídeo sobre programação"""

    query_gen = QueryGenerator(
        RAGConfig(max_keywords=5, max_context_chars=400),
        keyword_provider=_stub_keyword_provider,
    )
    result = query_gen.generate(whatsapp_content)

    assert isinstance(result, QueryResult)
    assert result.search_query
    assert "tecnologia" in result.search_query or "machine" in result.search_query
    assert len(result.keywords) <= 5
    assert result.context.startswith("03/10/2025")


def test_rag_config_validation(temp_dir: Path) -> None:
    """PipelineConfig should propagate valid RAG settings."""

    project_temp_dir = Path.cwd() / "tests" / "_tmp" / temp_dir.name
    zips_dir = project_temp_dir / "zips"
    posts_dir = project_temp_dir / "posts"
    zips_dir.mkdir(parents=True, exist_ok=True)
    posts_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        RAGConfig(enabled=True, max_context_chars=1000, exclude_recent_days=0),
        RAGConfig(enabled=False),
        RAGConfig(enabled=True, min_similarity=0.4, top_k=3, enable_cache=False),
    ]

    for rag_config in configs:
        config = PipelineConfig.with_defaults(
            zips_dir=zips_dir,
            posts_dir=posts_dir,
        )
        config.rag = rag_config

        assert config.rag.enabled == rag_config.enabled
        assert config.rag.top_k >= 1
        assert 0.0 <= config.rag.min_similarity <= 1.0


def test_post_rag_index_and_search(temp_dir: Path) -> None:
    """PostRAG should index newsletter posts and return semantic matches."""

    posts_root = temp_dir / "newsletter"
    post_a = _create_post(
        posts_root,
        stem="2025-10-01-team-sync",
        body="""# Daily Sync\n\nDiscutimos planejamento de IA e próximos passos.""",
    )
    post_b = _create_post(
        posts_root,
        stem="2025-10-02-research",
        body="""# Pesquisa\n\nFoco em machine learning aplicado a conversações.""",
    )

    rag_config = RAGConfig(
        enabled=True,
        top_k=3,
        min_similarity=0.0,
        exclude_recent_days=0,
        enable_cache=False,
        export_embeddings=False,
    )
    rag = PostRAG(posts_dir=posts_root, config=rag_config, cache_dir=temp_dir / "cache")

    stats = rag.update_index(force_rebuild=True)
    assert stats["posts_count"] == 2
    assert stats["chunks_count"] >= 2

    results = rag.search("machine learning roadmap")
    assert results, "Expected semantic search to return at least one chunk"

    top_node = results[0]
    metadata = getattr(top_node.node, "metadata", {}) or {}
    assert metadata.get("file_name") in {post_a.name, post_b.name}
    assert "machine" in top_node.node.get_content().lower()


def test_context_preparation_from_search_results(temp_dir: Path) -> None:
    """Search results should include enough context for downstream prompts."""

    posts_root = temp_dir / "newsletter"
    _create_post(
        posts_root,
        stem="2025-10-03-summary",
        body="""# Summary\n\nCobertura completa de iniciativas de IA generativa.""",
    )

    rag = PostRAG(
        posts_dir=posts_root,
        config=RAGConfig(enabled=True, min_similarity=0.0, exclude_recent_days=0),
        cache_dir=temp_dir / "cache",
    )
    rag.update_index(force_rebuild=True)

    results = rag.search("iniciativas de ia")
    context = "\n\n".join(node.node.get_content() for node in results)

    assert "IA" in context or "ia" in context
    assert len(context) <= rag.config.max_context_chars * len(results)


def test_whatsapp_data_processing_pipeline(temp_dir: Path) -> None:
    """Helper zip creation continues to behave for downstream ingestion."""

    zips_dir = temp_dir / "zips"
    zips_dir.mkdir()

    whatsapp_content = """03/10/2025 09:45 - Franklin: Vamos falar sobre IA
03/10/2025 09:46 - Franklin: https://youtu.be/example
03/10/2025 09:47 - Maria: Ótimo tópico para discussão
03/10/2025 09:48 - José: Tenho experiência com machine learning"""

    test_zip = zips_dir / "2025-10-03.zip"
    create_test_zip(whatsapp_content, test_zip, "conversation.txt")

    assert test_zip.exists()

    import zipfile

    with zipfile.ZipFile(test_zip, "r") as zf:
        files = zf.namelist()
        assert "conversation.txt" in files

        with zf.open("conversation.txt") as f:
            content = f.read().decode("utf-8")
            assert "Franklin" in content
            assert "IA" in content


def test_rag_performance_considerations(temp_dir: Path) -> None:
    """Smoke-test batching logic by building multiple posts."""

    posts_root = temp_dir / "newsletter"
    for day in range(1, 6):
        _create_post(
            posts_root,
            stem=f"2025-10-0{day}-topic",
            body=f"# Dia {day}\n\nDiscussão aprofundada sobre IA e dados {day}.",
        )

    rag = PostRAG(
        posts_dir=posts_root,
        config=RAGConfig(enabled=True, min_similarity=0.0, exclude_recent_days=0),
        cache_dir=temp_dir / "cache",
    )
    stats = rag.update_index(force_rebuild=True)

    assert stats["posts_count"] == 5
    assert stats["chunks_count"] >= 5

    results = rag.search("dados IA")
    assert len(results) <= rag.config.top_k
    assert all(node.score is None or 0 <= node.score <= 1 for node in results)
