"""Tests covering the Gemini embedding integration for the RAG subsystem."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from egregora.config import RAGConfig
from egregora.rag.core import NewsletterRAG


class DummyEmbeddingResponse:
    def __init__(self, values: list[float]):
        self.embedding = SimpleNamespace(values=values)


class DummyModels:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def embed_content(self, *, model: str, contents: str, config) -> DummyEmbeddingResponse:  # type: ignore[override]
        task_type = getattr(config, "task_type", "RETRIEVAL_DOCUMENT")
        self.calls.append((model, contents, task_type))
        base = 1.0 if task_type == "RETRIEVAL_QUERY" else float(len(self.calls))
        return DummyEmbeddingResponse([base, base + 0.5, base + 1.0])


class DummyGeminiClient:
    def __init__(self) -> None:
        self.models = DummyModels()


def _create_newsletter(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_newsletter_rag_uses_gemini_embeddings(tmp_path: Path) -> None:
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    cache_dir = tmp_path / "cache"

    _create_newsletter(
        newsletters_dir,
        "2024-10-01.md",
        """# Atualizações

Discussão sobre IA e automação.
""",
    )

    rag_config = RAGConfig(
        enabled=True,
        use_gemini_embeddings=True,
        min_similarity=0.0,
        embedding_dimension=3,
        exclude_recent_days=0,
    )

    dummy_client = DummyGeminiClient()

    rag = NewsletterRAG(
        newsletters_dir=newsletters_dir,
        cache_dir=cache_dir,
        config=rag_config,
        gemini_client=dummy_client,
    )

    rag.update_index(force_reindex=True)

    hits = rag.search(query="automação", top_k=1)

    assert hits, "Expected at least one hit using Gemini embeddings"
    assert hits[0].score > 0.0
    assert dummy_client.models.calls, "Embed API should have been invoked"


def test_gemini_embeddings_fall_back_without_client(tmp_path: Path) -> None:
    newsletters_dir = tmp_path / "newsletters"
    newsletters_dir.mkdir()
    cache_dir = tmp_path / "cache"

    _create_newsletter(
        newsletters_dir,
        "2024-10-02.md",
        "Conversa sobre aprendizado de máquina",
    )

    rag_config = RAGConfig(enabled=True, use_gemini_embeddings=True, min_similarity=0.0)

    rag = NewsletterRAG(
        newsletters_dir=newsletters_dir,
        cache_dir=cache_dir,
        config=rag_config,
        gemini_client=None,
    )

    rag.update_index(force_reindex=True)
    hits = rag.search(query="aprendizado", top_k=1)

    assert hits, "Fallback TF-IDF search should still return results"
