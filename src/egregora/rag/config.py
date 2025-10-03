"""Configuration options for the LlamaIndex-based RAG stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _default_mcp_args() -> tuple[str, ...]:
    return (
        "run",
        "python",
        "-m",
        "egregora.mcp_server.server",
    )


@dataclass(slots=True)
class RAGConfig:
    """Configuration for newsletter retrieval powered by LlamaIndex."""

    enabled: bool = False

    # Retrieval behaviour
    top_k: int = 5
    min_similarity: float = 0.65
    exclude_recent_days: int = 7

    # Query generation helpers
    max_context_chars: int = 1200
    max_keywords: int = 8

    # MCP integration
    use_mcp: bool = True
    mcp_command: str = "uv"
    mcp_args: tuple[str, ...] = field(default_factory=_default_mcp_args)

    # Chunking parameters (tokens)
    chunk_size: int = 1800
    chunk_overlap: int = 360

    # Embeddings
    embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 768
    enable_cache: bool = True
    cache_dir: Path = field(default_factory=lambda: Path("cache/embeddings"))

    # Vector store
    vector_store_type: str = "simple"
    persist_dir: Path = field(default_factory=lambda: Path("cache/vector_store"))
    collection_name: str = "newsletters"

    # Advanced options (placeholders for future iterations)
    use_semantic_chunking: bool = False
    enable_hybrid_search: bool = False
    use_batch_api: bool = False

    # Backwards-compatibility knobs used by QueryGenerator/tests
    use_gemini_embeddings: bool = True


__all__ = ["RAGConfig"]

